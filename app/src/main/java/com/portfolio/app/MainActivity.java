package com.portfolio.app;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.FrameLayout;
import java.io.*;
import java.net.*;
import java.util.Map;
import java.util.concurrent.*;

public class MainActivity extends Activity {

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private static final int FILE_REQ = 1001;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final Map<String, String> httpResults = new ConcurrentHashMap<>();

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
                    try {
                        URL u = new URL(url);
                        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
                        conn.setRequestProperty("User-Agent",
                            "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/108.0.0.0");
                        conn.setRequestProperty("Accept", "application/json, text/plain, */*");
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
                    }
                });
            }

            @JavascriptInterface
            public String fetch(String callbackId) {
                return httpResults.remove(callbackId);
            }
        }, "HttpBridge");

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
        });        webView.loadUrl("file:///android_asset/index.html");
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
