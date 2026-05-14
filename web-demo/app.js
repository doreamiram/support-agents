(function () {
  "use strict";

  var hint = document.getElementById("load-hint");
  var cardsEl = document.getElementById("cards");
  var fallbackEl = document.getElementById("fetch-fallback");

  function showFallback(message) {
    if (hint) hint.hidden = true;
    if (cardsEl) cardsEl.hidden = true;
    if (fallbackEl) {
      fallbackEl.textContent = message;
      fallbackEl.hidden = false;
    }
  }

  function render(data) {
    if (!data || !data.scenarios || !data.scenarios.length) {
      showFallback("Scenario data was empty or invalid.");
      return;
    }
    if (hint) hint.hidden = true;
    if (fallbackEl) fallbackEl.hidden = true;
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
      cardsEl.appendChild(article);
    });
    cardsEl.hidden = false;
  }

  fetch("demo-data.json", { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(render)
    .catch(function () {
      showFallback(
        "Could not load demo-data.json (file:// often blocks fetch). " +
          "Open this folder via a static server (for example: " +
          "Python: python -m http.server 8080 inside web-demo) " +
          "or deploy as static files on Vercel with project root set to web-demo."
      );
    });
})();
