package com.portfolio.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.view.ContextThemeWrapper;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

// WorkManager가 주기적으로(기본 6시간) 화면 없이 호출하는 백그라운드 갱신 작업.
// 실제 가격·목표주가 조회, 점수 계산, 워치리스트 자동 정리 로직은 전부 index.html(JS)에 있으며
// 이 클래스는 그 JS를 헤드리스 WebView에서 실행할 수 있게 NativeStorage/HttpBridge만 재현해 붙여준다.
// (MainActivity가 화면에 띄우는 WebView와는 별개의 인스턴스 — 앱이 열려 있어도 안전하게 병행 가능)
public class PortfolioUpdateWorker extends Worker {

    public PortfolioUpdateWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context appContext = getApplicationContext();
        CountDownLatch latch = new CountDownLatch(1);
        ExecutorService netExecutor = Executors.newCachedThreadPool();
        boolean[] ok = { false };
        WebView[] wvHolder = new WebView[1];

        new Handler(Looper.getMainLooper()).post(() -> {
            // 일부 기기에서 순수 ApplicationContext로 WebView를 생성하면 테마 부재로 죽는 사례가 있어
            // 액티비티와 동일한 테마를 씌운 ContextThemeWrapper를 사용한다.
            Context themedContext = new ContextThemeWrapper(appContext, R.style.Theme_App);
            WebView webView = new WebView(themedContext);
            wvHolder[0] = webView;

            WebSettings s = webView.getSettings();
            s.setJavaScriptEnabled(true);
            s.setDomStorageEnabled(true);
            s.setCacheMode(WebSettings.LOAD_NO_CACHE);

            SharedPreferences prefs = appContext.getSharedPreferences("porto", Context.MODE_PRIVATE);

            // 스토리지 브릿지 (MainActivity와 동일 키 "porto"를 공유 — 다음 앱 실행 시 그대로 반영됨)
            webView.addJavascriptInterface(new Object() {
                @JavascriptInterface public String get(String k) { return prefs.getString(k, null); }
                @JavascriptInterface public void set(String k, String v) { prefs.edit().putString(k, v).apply(); }
                @JavascriptInterface public void remove(String k) { prefs.edit().remove(k).apply(); }
            }, "NativeStorage");

            // HTTP 브릿지 (MainActivity의 HttpBridge와 동일한 구현)
            Map<String, String> httpResults = new ConcurrentHashMap<>();
            webView.addJavascriptInterface(new Object() {
                @JavascriptInterface
                public void get(String url, String callbackId) {
                    netExecutor.execute(() -> {
                        HttpURLConnection conn = null;
                        try {
                            URL u = new URL(url);
                            conn = (HttpURLConnection) u.openConnection();
                            conn.setRequestProperty("User-Agent",
                                "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/108.0.0.0");
                            conn.setRequestProperty("Accept", "application/json, text/plain, */*");
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
                            webView.post(() -> webView.evaluateJavascript(
                                "window.HttpBridge&&window.HttpBridge._deliver('" + callbackId + "')", null));
                        } catch (Exception e) {
                            webView.post(() -> webView.evaluateJavascript(
                                "window.HttpBridge&&window.HttpBridge._fail('" + callbackId + "')", null));
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

            // 헤드리스 완료 신호 브릿지 — index.html의 headlessUpdate()가 끝나면 호출됨
            webView.addJavascriptInterface(new Object() {
                @JavascriptInterface
                public void done(String summary) {
                    ok[0] = summary != null && summary.startsWith("ok");
                    latch.countDown();
                }
            }, "HeadlessBridge");

            webView.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView view, String url) {
                    view.evaluateJavascript("headlessUpdate();", null);
                }
            });

            webView.loadUrl("file:///android_asset/index.html");
        });

        try {
            // 가격·목표주가 조회는 종목 수만큼 순차 네트워크 호출이 필요해 다소 걸릴 수 있어 넉넉히 대기
            latch.await(2, TimeUnit.MINUTES);
        } catch (InterruptedException ignored) {
        }

        new Handler(Looper.getMainLooper()).post(() -> {
            if (wvHolder[0] != null) wvHolder[0].destroy();
        });
        netExecutor.shutdown();

        return ok[0] ? Result.success() : Result.retry();
    }
}
