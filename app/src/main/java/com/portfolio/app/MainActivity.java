package com.portfolio.app;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.view.View;
import android.view.Window;
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
import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity {

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private static final int FILE_REQ = 1001;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final Map<String, String> httpResults = new ConcurrentHashMap<>();
    private final Map<String, String> upbitResults = new ConcurrentHashMap<>();
    private final Map<String, String> kisResults = new ConcurrentHashMap<>();
    private final Map<String, String> kiwoomResults = new ConcurrentHashMap<>();

    private static final String KIS_REAL_URL = "https://openapi.koreainvestment.com:9443";
    private static final String KIS_DEMO_URL = "https://openapivts.koreainvestment.com:29443";
    private static final String KIWOOM_REAL_URL = "https://api.kiwoom.com";
    private static final String KIWOOM_MOCK_URL = "https://mockapi.kiwoom.com";

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
        // 시작 시 저장된 테마로 상태바·배경을 맞춰 페이지 로드 전 깜빡임을 줄인다
        if ("light".equals(prefs.getString("ui_theme", ""))) {
            applyBars("#EEF1F6", "#F4F6FA", true);
        } else {
            webView.setBackgroundColor(Color.parseColor("#04080F"));
        }

        // 화면 테마(다크/라이트) → 상태바·내비게이션바 색
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public void setBars(String status, String nav, boolean light) {
                applyBars(status, nav, light);
            }
        }, "UiBridge");

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
                        // FRED(Akamai)는 브라우저 UA의 비브라우저 요청을 차단 → Dalvik UA 사용
                        conn.setRequestProperty("User-Agent", url.contains("stlouisfed.org")
                            ? "Dalvik/2.1.0 (Linux; U; Android 12)"
                            : "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/108.0.0.0");
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
                        while ((line = br.readLine()) != null) sb.append(line).append('\n'); // 줄바꿈 보존 (CSV 파싱용)
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

        // 한국투자증권(KIS) REST API 브릿지 — OAuth2 토큰은 네이티브에서 발급·캐시하고, 시크릿은 JS로 노출하지 않음
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public boolean hasKeys() {
                String ak = prefs.getString("kis_app_key", "");
                String sk = prefs.getString("kis_app_secret", "");
                String cano = prefs.getString("kis_cano", "");
                return !ak.isEmpty() && !sk.isEmpty() && !cano.isEmpty();
            }

            @JavascriptInterface
            public void testConnection(boolean demo, String callbackId) {
                executor.execute(() -> {
                    try {
                        kisGetToken(getSharedPreferences("porto", MODE_PRIVATE), demo, true);
                        kisResults.put(callbackId, "{\"ok\":true}");
                    } catch (Exception e) {
                        kisResults.put(callbackId, errJson(e));
                    } finally {
                        webView.post(() -> webView.evaluateJavascript(
                            "window.KisBridge&&window.KisBridge._deliver('" + callbackId + "')", null));
                    }
                });
            }

            @JavascriptInterface
            public void placeOrder(boolean demo, String side, String pdno, String ordDvsn,
                                    String qty, String price, String callbackId) {
                kisPlaceOrder(demo, side, pdno, ordDvsn, qty, price, callbackId);
            }

            @JavascriptInterface
            public void balance(boolean demo, String callbackId) {
                kisBalance(demo, callbackId);
            }

            @JavascriptInterface
            public String fetch(String callbackId) {
                return kisResults.remove(callbackId);
            }
        }, "KisBridge");

        // 키움증권 REST API 브릿지 — 위와 동일한 방식(OAuth2 토큰 네이티브 발급·캐시)
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public boolean hasKeys() {
                String ak = prefs.getString("kiwoom_app_key", "");
                String sk = prefs.getString("kiwoom_app_secret", "");
                return !ak.isEmpty() && !sk.isEmpty();
            }

            @JavascriptInterface
            public void testConnection(boolean mock, String callbackId) {
                executor.execute(() -> {
                    try {
                        kiwoomGetToken(getSharedPreferences("porto", MODE_PRIVATE), mock, true);
                        kiwoomResults.put(callbackId, "{\"ok\":true}");
                    } catch (Exception e) {
                        kiwoomResults.put(callbackId, errJson(e));
                    } finally {
                        webView.post(() -> webView.evaluateJavascript(
                            "window.KiwoomBridge&&window.KiwoomBridge._deliver('" + callbackId + "')", null));
                    }
                });
            }

            @JavascriptInterface
            public void placeOrder(boolean mock, String side, String stkCd, String trdeTp,
                                    String qty, String price, String callbackId) {
                kiwoomPlaceOrder(mock, side, stkCd, trdeTp, qty, price, callbackId);
            }

            @JavascriptInterface
            public void balance(boolean mock, String callbackId) {
                kiwoomBalance(mock, callbackId);
            }

            @JavascriptInterface
            public String fetch(String callbackId) {
                return kiwoomResults.remove(callbackId);
            }
        }, "KiwoomBridge");

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

            // 앱을 열 때(=페이지 로드 완료 시)마다 워치리스트 가격·목표주가·자체 알고리즘을 자동 갱신
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                view.evaluateJavascript("autoUpdateOnLaunch();", null);
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

    private String readStream(InputStream is) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(is, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) sb.append(line);
        br.close();
        return sb.toString();
    }

    private String errJson(Exception e) {
        String msg = String.valueOf(e.getMessage()).replace("\\", "\\\\").replace("\"", "\\\"");
        return "{\"error\":{\"message\":\"" + msg + "\"}}";
    }

    // ── 한국투자증권(KIS) ──────────────────────────────────────────────
    // 접근토큰은 24시간 유효하며 재발급 요청이 잦으면 차단되므로, 만료 직전까지 로컬에 캐시해서 재사용한다.
    private String kisGetToken(SharedPreferences prefs, boolean demo, boolean forceRefresh) throws Exception {
        String tokenKey = demo ? "kis_token_demo" : "kis_token_real";
        String expKey = demo ? "kis_token_exp_demo" : "kis_token_exp_real";
        if (!forceRefresh) {
            String cached = prefs.getString(tokenKey, null);
            long exp = prefs.getLong(expKey, 0);
            if (cached != null && System.currentTimeMillis() < exp) return cached;
        }

        String appKey = prefs.getString("kis_app_key", "");
        String appSecret = prefs.getString("kis_app_secret", "");
        if (appKey.isEmpty() || appSecret.isEmpty()) {
            throw new IllegalStateException("한국투자증권 API 키가 설정되지 않았습니다.");
        }

        JSONObject body = new JSONObject();
        body.put("grant_type", "client_credentials");
        body.put("appkey", appKey);
        body.put("appsecret", appSecret);

        URL u = new URL((demo ? KIS_DEMO_URL : KIS_REAL_URL) + "/oauth2/tokenP");
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.getOutputStream().write(body.toString().getBytes("UTF-8"));

            int code = conn.getResponseCode();
            String resp = readStream(code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream());
            JSONObject j = new JSONObject(resp);
            if (!j.has("access_token")) {
                throw new IllegalStateException("토큰 발급 실패: " + j.optString("error_description", resp));
            }
            String token = j.getString("access_token");
            long expiresIn = j.optLong("expires_in", 86400);
            prefs.edit().putString(tokenKey, token)
                .putLong(expKey, System.currentTimeMillis() + Math.max(0, expiresIn - 300) * 1000L).apply();
            return token;
        } finally {
            conn.disconnect();
        }
    }

    private void kisPlaceOrder(boolean demo, String side, String pdno, String ordDvsn,
                                String qty, String price, String callbackId) {
        executor.execute(() -> {
            HttpURLConnection conn = null;
            try {
                SharedPreferences prefs = getSharedPreferences("porto", MODE_PRIVATE);
                String cano = prefs.getString("kis_cano", "");
                String prdtCd = prefs.getString("kis_prdt_cd", "");
                if (cano.isEmpty() || prdtCd.isEmpty()) {
                    throw new IllegalStateException("계좌번호(앞 8자리/상품코드)를 설정하세요.");
                }
                String appKey = prefs.getString("kis_app_key", "");
                String appSecret = prefs.getString("kis_app_secret", "");
                String token = kisGetToken(prefs, demo, false);

                boolean isSell = "sell".equals(side);
                String trId = demo ? (isSell ? "VTTC0011U" : "VTTC0012U") : (isSell ? "TTTC0011U" : "TTTC0012U");

                JSONObject body = new JSONObject();
                body.put("CANO", cano);
                body.put("ACNT_PRDT_CD", prdtCd);
                body.put("PDNO", pdno);
                body.put("ORD_DVSN", ordDvsn);
                body.put("ORD_QTY", qty);
                body.put("ORD_UNPR", price);
                body.put("EXCG_ID_DVSN_CD", "KRX");
                body.put("SLL_TYPE", isSell ? "01" : "");
                body.put("CNDT_PRIC", "");

                URL u = new URL((demo ? KIS_DEMO_URL : KIS_REAL_URL) + "/uapi/domestic-stock/v1/trading/order-cash");
                conn = (HttpURLConnection) u.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setRequestProperty("authorization", "Bearer " + token);
                conn.setRequestProperty("appkey", appKey);
                conn.setRequestProperty("appsecret", appSecret);
                conn.setRequestProperty("tr_id", trId);
                conn.setRequestProperty("custtype", "P");
                conn.setDoOutput(true);
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);
                conn.getOutputStream().write(body.toString().getBytes("UTF-8"));

                int code = conn.getResponseCode();
                kisResults.put(callbackId, readStream(code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream()));
            } catch (Exception e) {
                kisResults.put(callbackId, errJson(e));
            } finally {
                if (conn != null) conn.disconnect();
                webView.post(() -> webView.evaluateJavascript(
                    "window.KisBridge&&window.KisBridge._deliver('" + callbackId + "')", null));
            }
        });
    }

    // 주식잔고조회(inquire-balance). 연속조회(tr_cont M/F)는 최대 5페이지까지 이어 붙여 {rt_cd, rows, summary}로 돌려준다
    private String[] kisBalanceRequest(boolean demo, String token, String appKey, String appSecret,
                                       String cano, String prdtCd, String fk, String nk, boolean cont) throws Exception {
        String q = "CANO=" + URLEncoder.encode(cano, "UTF-8")
            + "&ACNT_PRDT_CD=" + URLEncoder.encode(prdtCd, "UTF-8")
            + "&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=02&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N"
            + "&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00"
            + "&CTX_AREA_FK100=" + URLEncoder.encode(fk, "UTF-8")
            + "&CTX_AREA_NK100=" + URLEncoder.encode(nk, "UTF-8");
        URL u = new URL((demo ? KIS_DEMO_URL : KIS_REAL_URL) + "/uapi/domestic-stock/v1/trading/inquire-balance?" + q);
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        try {
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("authorization", "Bearer " + token);
            conn.setRequestProperty("appkey", appKey);
            conn.setRequestProperty("appsecret", appSecret);
            conn.setRequestProperty("tr_id", demo ? "VTTC8434R" : "TTTC8434R");
            if (cont) conn.setRequestProperty("tr_cont", "N");
            conn.setRequestProperty("custtype", "P");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            int code = conn.getResponseCode();
            String resp = readStream(code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream());
            return new String[]{resp, conn.getHeaderField("tr_cont")};
        } finally {
            conn.disconnect();
        }
    }

    private void kisBalance(boolean demo, String callbackId) {
        executor.execute(() -> {
            try {
                SharedPreferences prefs = getSharedPreferences("porto", MODE_PRIVATE);
                String cano = prefs.getString("kis_cano", "");
                String prdtCd = prefs.getString("kis_prdt_cd", "");
                if (cano.isEmpty() || prdtCd.isEmpty()) {
                    throw new IllegalStateException("계좌번호(앞 8자리/상품코드)를 설정하세요.");
                }
                String appKey = prefs.getString("kis_app_key", "");
                String appSecret = prefs.getString("kis_app_secret", "");
                String token = kisGetToken(prefs, demo, false);

                JSONArray rows = new JSONArray();
                Object summary = null;
                String fk = "", nk = "";
                boolean cont = false;
                String error = null;
                for (int page = 0; page < 5; page++) {
                    String[] r = kisBalanceRequest(demo, token, appKey, appSecret, cano, prdtCd, fk, nk, cont);
                    JSONObject j = new JSONObject(r[0]);
                    String msgCd = j.optString("msg_cd", "");
                    if (page == 0 && ("EGW00123".equals(msgCd) || "EGW00121".equals(msgCd))) {
                        // 토큰 만료/무효 → 강제 재발급 후 1회 재시도
                        token = kisGetToken(prefs, demo, true);
                        r = kisBalanceRequest(demo, token, appKey, appSecret, cano, prdtCd, fk, nk, cont);
                        j = new JSONObject(r[0]);
                    }
                    if (!"0".equals(j.optString("rt_cd", "0"))) { error = r[0]; break; }
                    JSONArray o1 = j.optJSONArray("output1");
                    if (o1 != null) for (int i = 0; i < o1.length(); i++) rows.put(o1.get(i));
                    if (j.has("output2")) summary = j.get("output2");
                    String tc = r[1];
                    if (tc == null || !("M".equals(tc) || "F".equals(tc))) break;
                    fk = j.optString("ctx_area_fk100", "").trim();
                    nk = j.optString("ctx_area_nk100", "").trim();
                    cont = true;
                    Thread.sleep(600); // 초당 호출 제한(모의 2건/초)
                }
                if (error != null) {
                    kisResults.put(callbackId, error);
                } else {
                    JSONObject out = new JSONObject();
                    out.put("rt_cd", "0");
                    out.put("rows", rows);
                    if (summary != null) out.put("summary", summary);
                    kisResults.put(callbackId, out.toString());
                }
            } catch (Exception e) {
                kisResults.put(callbackId, errJson(e));
            } finally {
                webView.post(() -> webView.evaluateJavascript(
                    "window.KisBridge&&window.KisBridge._deliver('" + callbackId + "')", null));
            }
        });
    }

    // ── 키움증권 ──────────────────────────────────────────────────────
    private String kiwoomGetToken(SharedPreferences prefs, boolean mock, boolean forceRefresh) throws Exception {
        String tokenKey = mock ? "kiwoom_token_mock" : "kiwoom_token_real";
        String expKey = mock ? "kiwoom_token_exp_mock" : "kiwoom_token_exp_real";
        if (!forceRefresh) {
            String cached = prefs.getString(tokenKey, null);
            long exp = prefs.getLong(expKey, 0);
            if (cached != null && System.currentTimeMillis() < exp) return cached;
        }

        String appKey = prefs.getString("kiwoom_app_key", "");
        String appSecret = prefs.getString("kiwoom_app_secret", "");
        if (appKey.isEmpty() || appSecret.isEmpty()) {
            throw new IllegalStateException("키움증권 API 키가 설정되지 않았습니다.");
        }

        JSONObject body = new JSONObject();
        body.put("grant_type", "client_credentials");
        body.put("appkey", appKey);
        body.put("secretkey", appSecret);

        URL u = new URL((mock ? KIWOOM_MOCK_URL : KIWOOM_REAL_URL) + "/oauth2/token");
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json;charset=UTF-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.getOutputStream().write(body.toString().getBytes("UTF-8"));

            int code = conn.getResponseCode();
            String resp = readStream(code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream());
            JSONObject j = new JSONObject(resp);
            String token = j.has("token") ? j.optString("token") : j.optString("access_token");
            if (token == null || token.isEmpty()) {
                throw new IllegalStateException("토큰 발급 실패: " + j.optString("return_msg", resp));
            }
            // 정확한 만료시각 파싱 대신 보수적으로 20시간 캐시(만료되면 자동 재발급됨)
            prefs.edit().putString(tokenKey, token)
                .putLong(expKey, System.currentTimeMillis() + 20L * 3600 * 1000).apply();
            return token;
        } finally {
            conn.disconnect();
        }
    }

    private String kiwoomOrderRequest(boolean mock, String token, String side, String stkCd,
                                       String trdeTp, String qty, String price) throws Exception {
        JSONObject body = new JSONObject();
        body.put("dmst_stex_tp", "01"); // 01: KRX
        body.put("stk_cd", stkCd);
        body.put("ord_qty", Long.parseLong(qty));
        body.put("trde_tp", trdeTp);
        body.put("ord_uv", Long.parseLong(price));

        String apiId = "sell".equals(side) ? "kt10001" : "kt10000";
        URL u = new URL((mock ? KIWOOM_MOCK_URL : KIWOOM_REAL_URL) + "/api/dostk/ordr");
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json;charset=UTF-8");
            conn.setRequestProperty("api-id", apiId);
            conn.setRequestProperty("authorization", "Bearer " + token);
            conn.setRequestProperty("cont-yn", "N");
            conn.setRequestProperty("next-key", "");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.getOutputStream().write(body.toString().getBytes("UTF-8"));

            int code = conn.getResponseCode();
            return readStream(code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream());
        } finally {
            conn.disconnect();
        }
    }

    private void kiwoomPlaceOrder(boolean mock, String side, String stkCd, String trdeTp,
                                   String qty, String price, String callbackId) {
        executor.execute(() -> {
            try {
                SharedPreferences prefs = getSharedPreferences("porto", MODE_PRIVATE);
                String token = kiwoomGetToken(prefs, mock, false);
                String resp = kiwoomOrderRequest(mock, token, side, stkCd, trdeTp, qty, price);
                JSONObject j = new JSONObject(resp);
                if (j.optInt("return_code", 0) == 3) {
                    // return_code 3 = 토큰 만료/무효 (HTTP는 200으로 옴) → 강제 재발급 후 1회 재시도
                    token = kiwoomGetToken(prefs, mock, true);
                    resp = kiwoomOrderRequest(mock, token, side, stkCd, trdeTp, qty, price);
                }
                kiwoomResults.put(callbackId, resp);
            } catch (Exception e) {
                kiwoomResults.put(callbackId, errJson(e));
            } finally {
                webView.post(() -> webView.evaluateJavascript(
                    "window.KiwoomBridge&&window.KiwoomBridge._deliver('" + callbackId + "')", null));
            }
        });
    }

    // 계좌평가잔고내역(kt00018). 연속조회(cont-yn/next-key)는 최대 5페이지까지 이어 붙인다
    private String[] kiwoomAcntRequest(boolean mock, String token, String apiId, JSONObject body,
                                       String contYn, String nextKey) throws Exception {
        URL u = new URL((mock ? KIWOOM_MOCK_URL : KIWOOM_REAL_URL) + "/api/dostk/acnt");
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json;charset=UTF-8");
            conn.setRequestProperty("api-id", apiId);
            conn.setRequestProperty("authorization", "Bearer " + token);
            conn.setRequestProperty("cont-yn", contYn);
            conn.setRequestProperty("next-key", nextKey);
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.getOutputStream().write(body.toString().getBytes("UTF-8"));
            int code = conn.getResponseCode();
            String resp = readStream(code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream());
            return new String[]{resp, conn.getHeaderField("cont-yn"), conn.getHeaderField("next-key")};
        } finally {
            conn.disconnect();
        }
    }

    private void kiwoomBalance(boolean mock, String callbackId) {
        executor.execute(() -> {
            try {
                SharedPreferences prefs = getSharedPreferences("porto", MODE_PRIVATE);
                String token = kiwoomGetToken(prefs, mock, false);
                JSONObject body = new JSONObject();
                body.put("qry_tp", "1");          // 1: 합산
                body.put("dmst_stex_tp", "KRX");
                JSONArray rows = new JSONArray();
                JSONObject first = null;
                String contYn = "N", nextKey = "", error = null;
                for (int page = 0; page < 5; page++) {
                    String[] r = kiwoomAcntRequest(mock, token, "kt00018", body, contYn, nextKey);
                    JSONObject j = new JSONObject(r[0]);
                    if (page == 0 && j.optInt("return_code", 0) == 3) {
                        // return_code 3 = 토큰 만료/무효 → 강제 재발급 후 1회 재시도
                        token = kiwoomGetToken(prefs, mock, true);
                        r = kiwoomAcntRequest(mock, token, "kt00018", body, contYn, nextKey);
                        j = new JSONObject(r[0]);
                    }
                    if (j.optInt("return_code", 0) != 0) { error = r[0]; break; }
                    if (first == null) first = j;
                    JSONArray a = j.optJSONArray("acnt_evlt_remn_indv_tot");
                    if (a != null) for (int i = 0; i < a.length(); i++) rows.put(a.get(i));
                    if (!"Y".equals(r[1]) || r[2] == null || r[2].isEmpty()) break;
                    contYn = "Y";
                    nextKey = r[2];
                    Thread.sleep(300);
                }
                if (error != null) {
                    kiwoomResults.put(callbackId, error);
                } else {
                    if (first == null) first = new JSONObject();
                    first.put("return_code", 0);
                    first.put("acnt_evlt_remn_indv_tot", rows);
                    kiwoomResults.put(callbackId, first.toString());
                }
            } catch (Exception e) {
                kiwoomResults.put(callbackId, errJson(e));
            } finally {
                webView.post(() -> webView.evaluateJavascript(
                    "window.KiwoomBridge&&window.KiwoomBridge._deliver('" + callbackId + "')", null));
            }
        });
    }

    // 상태바·내비게이션바 색과 아이콘 밝기 (라이트 테마는 어두운 아이콘)
    private void applyBars(String status, String nav, boolean light) {
        runOnUiThread(() -> {
            try {
                Window w = getWindow();
                w.setStatusBarColor(Color.parseColor(status));
                w.setNavigationBarColor(Color.parseColor(nav));
                w.getDecorView().setBackgroundColor(Color.parseColor(status));
                if (webView != null) webView.setBackgroundColor(Color.parseColor(status));
                View d = w.getDecorView();
                int f = d.getSystemUiVisibility();
                int lightFlags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
                if (Build.VERSION.SDK_INT >= 26) lightFlags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                d.setSystemUiVisibility(light ? (f | lightFlags) : (f & ~lightFlags));
            } catch (Exception ignored) {
            }
        });
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
