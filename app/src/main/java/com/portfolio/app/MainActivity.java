package com.portfolio.app;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.*;
import android.widget.FrameLayout;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONObject;

public class MainActivity extends Activity {

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private static final int FILE_REQ = 1001;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final Map<String, String> httpResults = new ConcurrentHashMap<>();
    private final Map<String, String> upbitResults = new ConcurrentHashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout frame = new FrameLayout(this);
        webView = new WebView(this);
        frame.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        setContentView(frame);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);

        SharedPreferences prefs = getSharedPreferences("porto", MODE_PRIVATE);

        // 스토리지 브릿지
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface public String get(String k) { return prefs.getString(k, null); }
            @JavascriptInterface public void set(String k, String v) { prefs.edit().putString(k,v).apply(); }
            @JavascriptInterface public void remove(String k) { prefs.edit().remove(k).apply(); }
        }, "NativeStorage");

        // HTTP 브릿지 (CORS 우회, Naver/Yahoo Finance 크롤링용)
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public void get(String url, String callbackId) {
                executor.execute(() -> {
                    HttpURLConnection conn = null;
                    try {
                        URL u = new URL(url);
                        conn = (HttpURLConnection) u.openConnection();
                        conn.setRequestProperty("User-Agent",
                            "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/108.0.0.0");
                        conn.setRequestProperty("Accept", "application/json, text/plain, */*");
                        // 네이버 API는 Referer 헤더 요구
                        if (url.contains("naver.com")) {
                            conn.setRequestProperty("Referer", "https://m.stock.naver.com/");
                        }
                        conn.setConnectTimeout(8000);
                        conn.setReadTimeout(8000);
                        conn.setInstanceFollowRedirects(true);

                        BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), "UTF-8"));
                        StringBuilder sb = new StringBuilder();
                        String line;
                        while ((line = br.readLine()) != null) sb.append(line);
                        br.close();

                        httpResults.put(callbackId, sb.toString());
                        final String id = callbackId;
                        webView.post(() -> webView.evaluateJavascript(
                            "window.HttpBridge&&window.HttpBridge._deliver('" + id + "')", null));
                    } catch (Exception e) {
                        final String id = callbackId;
                        webView.post(() -> webView.evaluateJavascript(
                            "window.HttpBridge&&window.HttpBridge._fail('" + id + "')", null));
                    } finally {
                        if (conn != null) conn.disconnect();
                    }
                });
            }

            @JavascriptInterface
            public String fetch(String callbackId) {
                return httpResults.remove(callbackId);
            }
        }, "HttpBridge");

        // 업비트 Open API 브릿지 (JWT 서명은 전부 네이티브에서 처리 — 비밀키가 JS로 노출되지 않음)
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public boolean hasKeys() {
                String ak = prefs.getString("upbit_access_key", "");
                String sk = prefs.getString("upbit_secret_key", "");
                return !ak.isEmpty() && !sk.isEmpty();
            }

            @JavascriptInterface
            public void accounts(String callbackId) {
                upbitRequest("GET", "/v1/accounts", null, callbackId);
            }

            @JavascriptInterface
            public void orderChance(String market, String callbackId) {
                LinkedHashMap<String, String> q = new LinkedHashMap<>();
                q.put("market", market);
                upbitRequest("GET", "/v1/orders/chance", q, callbackId);
            }

            @JavascriptInterface
            public void orderStatus(String uuid, String callbackId) {
                LinkedHashMap<String, String> q = new LinkedHashMap<>();
                q.put("uuid", uuid);
                upbitRequest("GET", "/v1/order", q, callbackId);
            }

            @JavascriptInterface
            public void cancelOrder(String uuid, String callbackId) {
                LinkedHashMap<String, String> q = new LinkedHashMap<>();
                q.put("uuid", uuid);
                upbitRequest("DELETE", "/v1/order", q, callbackId);
            }

            @JavascriptInterface
            public void placeOrder(String market, String side, String volume, String price,
                                    String ordType, String callbackId) {
                LinkedHashMap<String, String> q = new LinkedHashMap<>();
                q.put("market", market);
                q.put("side", side);
                if (volume != null && !volume.isEmpty()) q.put("volume", volume);
                if (price != null && !price.isEmpty()) q.put("price", price);
                q.put("ord_type", ordType);
                upbitRequest("POST", "/v1/orders", q, callbackId);
            }

            @JavascriptInterface
            public String fetch(String callbackId) {
                return upbitResults.remove(callbackId);
            }
        }, "UpbitBridge");

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView wv, ValueCallback<Uri[]> cb,
                                              FileChooserParams params) {
                fileCallback = cb;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.setType("image/*");
                startActivityForResult(Intent.createChooser(intent, "사진 선택"), FILE_REQ);
                return true;
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, String url) {
                if (url.startsWith("file://")) {
                    v.loadUrl(url);
                    return true;
                }
                // http/https → 시스템 브라우저로 열기
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    startActivity(intent);
                    return true;
                }
                return false;
            }
        });

        webView.loadUrl("file:///android_asset/index.html");
    }

    // 업비트 Open API 서명 요청: JWT(HS256) + (파라미터가 있으면) SHA-512 query_hash 클레임 포함
    private void upbitRequest(String method, String path, LinkedHashMap<String, String> params, String callbackId) {
        executor.execute(() -> {
            HttpURLConnection conn = null;
            try {
                SharedPreferences prefs = getSharedPreferences("porto", MODE_PRIVATE);
                String accessKey = prefs.getString("upbit_access_key", "");
                String secretKey = prefs.getString("upbit_secret_key", "");
                if (accessKey.isEmpty() || secretKey.isEmpty()) {
                    throw new IllegalStateException("업비트 API 키가 설정되지 않았습니다.");
                }

                String queryString = null;
                if (params != null && !params.isEmpty()) {
                    StringBuilder qs = new StringBuilder();
                    for (Map.Entry<String, String> e : params.entrySet()) {
                        if (qs.length() > 0) qs.append('&');
                        qs.append(e.getKey()).append('=').append(e.getValue());
                    }
                    queryString = qs.toString();
                }

                String jwt = buildUpbitJwt(accessKey, secretKey, queryString);

                String urlStr = "https://api.upbit.com" + path;
                if (!"POST".equals(method) && queryString != null) urlStr += "?" + queryString;

                URL u = new URL(urlStr);
                conn = (HttpURLConnection) u.openConnection();
                conn.setRequestMethod(method);
                conn.setRequestProperty("Authorization", "Bearer " + jwt);
                conn.setRequestProperty("Accept", "application/json");
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);

                if ("POST".equals(method) && params != null) {
                    conn.setDoOutput(true);
                    conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    JSONObject body = new JSONObject();
                    for (Map.Entry<String, String> e : params.entrySet()) body.put(e.getKey(), e.getValue());
                    conn.getOutputStream().write(body.toString().getBytes("UTF-8"));
                }

                int code = conn.getResponseCode();
                InputStream is = (code >= 200 && code < 300) ? conn.getInputStream() : conn.getErrorStream();
                BufferedReader br = new BufferedReader(new InputStreamReader(is, "UTF-8"));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
                br.close();
                upbitResults.put(callbackId, sb.toString());
            } catch (Exception e) {
                String msg = String.valueOf(e.getMessage()).replace("\\", "\\\\").replace("\"", "\\\"");
                upbitResults.put(callbackId, "{\"error\":{\"message\":\"" + msg + "\"}}");
            } finally {
                if (conn != null) conn.disconnect();
                webView.post(() -> webView.evaluateJavascript(
                    "window.UpbitBridge&&window.UpbitBridge._deliver('" + callbackId + "')", null));
            }
        });
    }

    private String buildUpbitJwt(String accessKey, String secretKey, String queryString) throws Exception {
        String nonce = UUID.randomUUID().toString();
        StringBuilder payload = new StringBuilder();
        payload.append("{\"access_key\":\"").append(accessKey).append("\",\"nonce\":\"").append(nonce).append('"');
        if (queryString != null) {
            MessageDigest sha512 = MessageDigest.getInstance("SHA-512");
            byte[] hash = sha512.digest(queryString.getBytes("UTF-8"));
            StringBuilder hex = new StringBuilder();
            for (byte b : hash) hex.append(String.format("%02x", b));
            payload.append(",\"query_hash\":\"").append(hex).append("\",\"query_hash_alg\":\"SHA512\"");
        }
        payload.append('}');

        String header = base64Url("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes("UTF-8"));
        String body = base64Url(payload.toString().getBytes("UTF-8"));
        String signingInput = header + "." + body;

        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secretKey.getBytes("UTF-8"), "HmacSHA256"));
        String sig = base64Url(mac.doFinal(signingInput.getBytes("UTF-8")));
        return signingInput + "." + sig;
    }

    private String base64Url(byte[] data) {
        return Base64.encodeToString(data, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        if (req == FILE_REQ) {
            Uri[] uris = null;
            if (res == RESULT_OK && data != null) uris = new Uri[]{ data.getData() };
            if (fileCallback != null) { fileCallback.onReceiveValue(uris); fileCallback = null; }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
