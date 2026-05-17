(function () {
  "use strict";

  var BACKEND_DEMO_URL = "http://127.0.0.1:8000/api/demo/scenarios";
  var STATIC_DEMO_URL = "demo-data.json";

  var hint = document.getElementById("load-hint");
  var cardsEl = document.getElementById("cards");
  var fallbackEl = document.getElementById("fetch-fallback");
  var runLiveButton = document.getElementById("run-live-demo");
  var liveDemoMessage = document.getElementById("live-demo-message");
  var backendMode = document.getElementById("backend-mode");
  var lastRunStatus = document.getElementById("last-run-status");
  var scenarioCount = document.getElementById("scenario-count");
  var testBaseline = document.getElementById("test-baseline");

  var staticSnapshot = null;

  function setText(el, value) {
    if (el) el.textContent = value;
  }

  function setRunSummary(data, modeLabel, statusLabel) {
    var scenarios = data && data.scenarios ? data.scenarios : [];
    var meta = data && data.meta ? data.meta : {};
    setText(backendMode, modeLabel);
    setText(lastRunStatus, statusLabel);
    setText(scenarioCount, String(scenarios.length));
    setText(testBaseline, meta.tests_baseline || "549/549");
  }

  function showFallback(message) {
    if (hint) hint.hidden = true;
    if (cardsEl) cardsEl.hidden = true;
    if (fallbackEl) {
      fallbackEl.textContent = message;
      fallbackEl.hidden = false;
    }
  }

  function showMessage(message) {
    setText(liveDemoMessage, message);
  }

  function render(data, modeLabel, statusLabel) {
    if (!data || !data.scenarios || !data.scenarios.length) {
      showFallback("Scenario data was empty or invalid.");
      return;
    }
    if (hint) hint.hidden = true;
    if (fallbackEl) fallbackEl.hidden = true;
    setRunSummary(data, modeLabel, statusLabel);
    cardsEl.innerHTML = "";
    data.scenarios.forEach(function (s) {
      var article = document.createElement("article");
      article.className = "card";
      article.setAttribute("data-scenario-id", s.id || "");

      var badge = document.createElement("div");
      badge.className = "badge";
      badge.textContent = "status: " + (s.status || "—");
      article.appendChild(badge);

      var h = document.createElement("h3");
      h.textContent = s.title || "Scenario";
      article.appendChild(h);

      var dl = document.createElement("dl");

      function row(label, value) {
        var dt = document.createElement("dt");
        dt.textContent = label;
        var dd = document.createElement("dd");
        dd.textContent = value == null ? "—" : String(value);
        dl.appendChild(dt);
        dl.appendChild(dd);
      }

      row("action", s.action);
      row("reason", s.reason);
      row("key result", s.key_result);
      row("PRD capability", s.prd_capability);
      row("simulated", s.simulated);
      row("real", s.real);

      article.appendChild(dl);

      if (Array.isArray(s.execution_trace) && s.execution_trace.length) {
        var traceHeading = document.createElement("h4");
        traceHeading.textContent = "Execution trace";
        article.appendChild(traceHeading);

        var trace = document.createElement("ol");
        trace.className = "execution-trace";
        s.execution_trace.forEach(function (step) {
          var item = document.createElement("li");
          item.textContent = step;
          trace.appendChild(item);
        });
        article.appendChild(trace);
      }

      cardsEl.appendChild(article);
    });
    cardsEl.hidden = false;
  }

  function loadStaticSnapshot(message) {
    return fetch(STATIC_DEMO_URL, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        staticSnapshot = data;
        render(data, "Static fallback", "Static snapshot");
        showMessage(message || "Static snapshot loaded. Run the live backend demo when FastAPI is available.");
        return data;
      });
  }

  function runLiveDemo() {
    if (runLiveButton) runLiveButton.disabled = true;
    showMessage("Running live backend demo...");
    setText(lastRunStatus, "Running");

    fetch(BACKEND_DEMO_URL, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        render(data, "Live", "Live run completed");
        showMessage("Live backend run completed.");
      })
      .catch(function () {
        if (staticSnapshot) {
          render(staticSnapshot, "Static fallback", "Live backend unavailable");
          showMessage("Live backend unavailable, showing static snapshot.");
          return;
        }
        loadStaticSnapshot("Live backend unavailable, showing static snapshot.").catch(function () {
          showFallback(
            "Live backend unavailable, and static demo-data.json could not be loaded. " +
              "Open this folder via a static server such as: " +
              "Python: python -m http.server 8080 inside web-demo."
          );
        });
      })
      .finally(function () {
        if (runLiveButton) runLiveButton.disabled = false;
      });
  }

  if (runLiveButton) {
    runLiveButton.addEventListener("click", runLiveDemo);
  }

  loadStaticSnapshot()
    .then(function (res) {
      return res;
    })
    .catch(function () {
      showFallback(
        "Could not load demo-data.json (file:// often blocks fetch). " +
          "Open this folder via a static server (for example: " +
          "Python: python -m http.server 8080 inside web-demo) " +
          "or deploy as static files on Vercel with project root set to web-demo."
      );
    });
})();
