/*!
 * django-bikram Bikram Sambat date picker.
 *
 * No dependencies, no build step, no CDN. Attaches to any input carrying the
 * class "bs-datepicker" and reads its configuration from data- attributes, so
 * several fields on one page can differ in language and numerals.
 *
 * The calendar table below is generated from the same verified data the Python
 * side uses (django_bikram.django.forms.encode_verified_calendar); a test in
 * the package asserts this file still matches it, so the two cannot drift.
 */
(function () {
  "use strict";

  // Twelve chars per BS year from MIN_YEAR, each holding (days - 29).
  var MONTHS = "223321101011232321110012132321110102223222101011223321101011232321110012222322011011223222101011223321101011232321110012222322011011223222101011232321101011232321110012222322011011223222101011232321110011232321110102223222101011223222101011232321110011232321110102223222101011223222101011232321110012132321110102223222101011223321101011232321110012132321110102223222101011223321101011232321110012222322011002223222101011223321101011232321110012222322011011223222101011223321101011232321110012222322011011223222101011232321101011232321110102222322101011223222101011232321110011232321110102222322101011223222101011232321110012132321110102223222101011223231101011232321110012132321110102223222101011223321101011232321110012132322011002223222101011223321101011232321110012222322011011223222101011223321101011232321110012222322011011223222101011232321101011232321110012222322101011223222101011232321110011232321110102222322101011223222101011232321110011232321110102223222101011223231101011232321110012132321110102223222101011223321101011232321110012222322010102223222101011223321101011232321110012222322011002223222101011223321101011232321110012222322011011223222101011232321101011232321110012222322101011223222101011232321110011232321110102222322101011223222101011232321110011232321110102223222101011223222101011223221110111";
  var MIN_YEAR = 1975;
  var MONTHS_IN_YEAR = 12;
  var MAX_YEAR = MIN_YEAR + MONTHS.length / MONTHS_IN_YEAR - 1;
  // 1 Baishakh MIN_YEAR = 13 April 1918, as UTC ms. All date maths is done in
  // UTC so a browser's local timezone can never shift the calendar by a day.
  var ANCHOR = Date.UTC(1918, 3, 13);
  var DAY_MS = 86400000;
  // Nepal Standard Time, UTC+05:45 -- fixed, no DST, so "today in Nepal" is
  // just a shifted UTC read. Matches django_bikram.date.NEPAL_TZ.
  var NPT_OFFSET_MS = (5 * 60 + 45) * 60000;

  var NAMES = {
    en: {
      months: ["Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
               "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"],
      weekdays: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      today: "Today", clear: "Clear"
    },
    ne: {
      months: ["वैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज",
               "कात्तिक", "मंसिर", "पुस", "माघ", "फागुन", "चैत"],
      weekdays: ["आइत", "सोम", "मङ्गल", "बुध", "बिही", "शुक्र", "शनि"],
      today: "आज", clear: "खाली"
    }
  };
  var DEV_DIGITS = "०१२३४५६७८९";

  // --- calendar arithmetic (mirrors django_bikram.convert) ------------------

  function daysInMonth(year, month) {
    return MONTHS.charCodeAt((year - MIN_YEAR) * MONTHS_IN_YEAR + month - 1) - 48 + 29;
  }

  // Cumulative days from ANCHOR to 1 Baishakh of each year, built once.
  var YEAR_OFFSET = (function () {
    var offsets = [], running = 0;
    for (var y = MIN_YEAR; y <= MAX_YEAR; y++) {
      offsets.push(running);
      for (var m = 1; m <= MONTHS_IN_YEAR; m++) running += daysInMonth(y, m);
    }
    offsets.push(running); // sentinel: one past the table
    return offsets;
  })();

  function bsToAd(year, month, day) {
    var offset = YEAR_OFFSET[year - MIN_YEAR] + day - 1;
    for (var m = 1; m < month; m++) offset += daysInMonth(year, m);
    return new Date(ANCHOR + offset * DAY_MS);
  }

  function adToBs(date) {
    var delta = Math.floor((date.getTime() - ANCHOR) / DAY_MS);
    if (delta < 0 || delta >= YEAR_OFFSET[YEAR_OFFSET.length - 1]) return null;
    var lo = 0, hi = YEAR_OFFSET.length - 2;
    while (lo < hi) {
      var mid = Math.ceil((lo + hi) / 2);
      if (YEAR_OFFSET[mid] <= delta) lo = mid; else hi = mid - 1;
    }
    var year = MIN_YEAR + lo, rest = delta - YEAR_OFFSET[lo];
    for (var m = 1; m <= MONTHS_IN_YEAR; m++) {
      var len = daysInMonth(year, m);
      if (rest < len) return { year: year, month: m, day: rest + 1 };
      rest -= len;
    }
    return null;
  }

  function todayBs() {
    return adToBs(new Date(Date.now() + NPT_OFFSET_MS));
  }

  // --- formatting (mirrors django_bikram.formatting) ------------------------

  function pad(n, width) {
    var s = String(n);
    while (s.length < width) s = "0" + s;
    return s;
  }

  function toDevanagari(text) {
    return text.replace(/[0-9]/g, function (d) { return DEV_DIGITS[+d]; });
  }

  function format(bs, fmt, lang, numerals) {
    var names = NAMES[lang] || NAMES.en;
    var weekday = (bsToAd(bs.year, bs.month, bs.day).getUTCDay());
    var out = fmt.replace(/%(-?)([A-Za-z%])/g, function (all, dash, code) {
      var padded = !dash;
      switch (code) {
        case "%": return "%";
        case "Y": return pad(bs.year, 4);
        case "y": return pad(bs.year % 100, 2);
        case "m": return padded ? pad(bs.month, 2) : String(bs.month);
        case "d": return padded ? pad(bs.day, 2) : String(bs.day);
        case "B": return names.months[bs.month - 1];
        case "b": return names.months[bs.month - 1];
        case "A": return names.weekdays[weekday];
        case "a": return names.weekdays[weekday];
        default: return all;
      }
    });
    return numerals === "devanagari" ? toDevanagari(out) : out;
  }

  // --- the picker -----------------------------------------------------------

  function build(input) {
    var lang = input.getAttribute("data-bs-lang") || "en";
    var numerals = input.getAttribute("data-bs-numerals") || "ascii";
    var fmt = input.getAttribute("data-bs-format") || "%Y-%m-%d";
    var names = NAMES[lang] || NAMES.en;

    var panel = document.createElement("div");
    panel.className = "bs-dp-panel";
    panel.setAttribute("role", "dialog");
    panel.hidden = true;

    var view = null; // {year, month} currently displayed

    function selected() {
      var iso = input.getAttribute("data-bs-date");
      if (!iso) return null;
      var parts = iso.split("-");
      if (parts.length !== 3) return null;
      return { year: +parts[0], month: +parts[1], day: +parts[2] };
    }

    function clamp(v) {
      if (v.year < MIN_YEAR) return { year: MIN_YEAR, month: 1 };
      if (v.year > MAX_YEAR) return { year: MAX_YEAR, month: MONTHS_IN_YEAR };
      return v;
    }

    function shiftMonth(step) {
      var m = view.month + step, y = view.year;
      if (m < 1) { m = MONTHS_IN_YEAR; y--; }
      if (m > MONTHS_IN_YEAR) { m = 1; y++; }
      if (y < MIN_YEAR || y > MAX_YEAR) return;
      view = { year: y, month: m };
      render();
    }

    function choose(day) {
      var bs = { year: view.year, month: view.month, day: day };
      input.value = format(bs, fmt, lang, numerals);
      input.setAttribute("data-bs-date",
        pad(bs.year, 4) + "-" + pad(bs.month, 2) + "-" + pad(bs.day, 2));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      close();
      input.focus();
    }

    function render() {
      panel.textContent = "";

      var head = document.createElement("div");
      head.className = "bs-dp-head";
      head.appendChild(navButton("‹", function () { shiftMonth(-1); }, "Previous month"));

      var title = document.createElement("div");
      title.className = "bs-dp-title";

      var monthSelect = document.createElement("select");
      monthSelect.setAttribute("aria-label", "Month");
      names.months.forEach(function (label, i) {
        var opt = document.createElement("option");
        opt.value = String(i + 1);
        opt.textContent = label;
        if (i + 1 === view.month) opt.selected = true;
        monthSelect.appendChild(opt);
      });
      monthSelect.addEventListener("change", function () {
        view = { year: view.year, month: +monthSelect.value };
        render();
      });

      var yearSelect = document.createElement("select");
      yearSelect.setAttribute("aria-label", "Year");
      for (var y = MIN_YEAR; y <= MAX_YEAR; y++) {
        var opt = document.createElement("option");
        opt.value = String(y);
        opt.textContent = numerals === "devanagari" ? toDevanagari(String(y)) : String(y);
        if (y === view.year) opt.selected = true;
        yearSelect.appendChild(opt);
      }
      yearSelect.addEventListener("change", function () {
        view = { year: +yearSelect.value, month: view.month };
        render();
      });

      title.appendChild(monthSelect);
      title.appendChild(yearSelect);
      head.appendChild(title);
      head.appendChild(navButton("›", function () { shiftMonth(1); }, "Next month"));
      panel.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "bs-dp-grid";
      names.weekdays.forEach(function (label) {
        var cell = document.createElement("div");
        cell.className = "bs-dp-weekday";
        cell.textContent = label;
        grid.appendChild(cell);
      });

      // Nepali calendars start the week on Sunday, which is getUTCDay() === 0.
      var lead = bsToAd(view.year, view.month, 1).getUTCDay();
      for (var i = 0; i < lead; i++) {
        grid.appendChild(document.createElement("div"));
      }

      var sel = selected();
      var now = todayBs();
      var total = daysInMonth(view.year, view.month);
      for (var d = 1; d <= total; d++) {
        grid.appendChild(dayButton(d, sel, now));
      }
      panel.appendChild(grid);

      var foot = document.createElement("div");
      foot.className = "bs-dp-foot";
      foot.appendChild(textButton(names.today, function () {
        var t = todayBs();
        if (!t) return;
        view = { year: t.year, month: t.month };
        choose(t.day);
      }));
      foot.appendChild(textButton(names.clear, function () {
        input.value = "";
        input.removeAttribute("data-bs-date");
        input.dispatchEvent(new Event("change", { bubbles: true }));
        close();
      }));
      panel.appendChild(foot);
    }

    function dayButton(d, sel, now) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bs-dp-day";
      btn.textContent = numerals === "devanagari" ? toDevanagari(String(d)) : String(d);
      if (sel && sel.year === view.year && sel.month === view.month && sel.day === d) {
        btn.classList.add("is-selected");
        btn.setAttribute("aria-current", "date");
      }
      if (now && now.year === view.year && now.month === view.month && now.day === d) {
        btn.classList.add("is-today");
      }
      btn.addEventListener("click", function () { choose(d); });
      return btn;
    }

    function navButton(label, handler, aria) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bs-dp-nav";
      btn.textContent = label;
      btn.setAttribute("aria-label", aria);
      btn.addEventListener("click", handler);
      return btn;
    }

    function textButton(label, handler) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bs-dp-text";
      btn.textContent = label;
      btn.addEventListener("click", handler);
      return btn;
    }

    function open() {
      if (!panel.hidden) return;
      view = clamp(selected() || todayBs() || { year: MIN_YEAR, month: 1 });
      render();
      panel.hidden = false;
      document.addEventListener("mousedown", onOutside, true);
      document.addEventListener("keydown", onKey, true);
    }

    function close() {
      panel.hidden = true;
      document.removeEventListener("mousedown", onOutside, true);
      document.removeEventListener("keydown", onKey, true);
    }

    function onOutside(event) {
      if (!panel.contains(event.target) && event.target !== input) close();
    }

    function onKey(event) {
      if (event.key === "Escape") { close(); input.focus(); }
    }

    var wrap = document.createElement("span");
    wrap.className = "bs-dp-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(panel);

    input.addEventListener("focus", open);
    input.addEventListener("click", open);
  }

  function init(root) {
    var inputs = (root || document).querySelectorAll("input.bs-datepicker");
    Array.prototype.forEach.call(inputs, function (input) {
      if (input.dataset.bsDpReady) return;
      input.dataset.bsDpReady = "1";
      build(input);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(); });
  } else {
    init();
  }
  // Exposed so dynamically added forms (admin inlines, htmx swaps) can re-scan.
  window.djangoBikramDatePicker = { init: init, bsToAd: bsToAd, adToBs: adToBs };
})();
