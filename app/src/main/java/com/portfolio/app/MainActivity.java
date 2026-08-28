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
                        // 네이버 API는 Referer 헤더 요구
                        if (url.contains("naver.com")) {
                            conn.setRequestProperty("Referer", "https://m.stock.naver.com/");
                        }
