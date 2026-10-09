/* Render-blocking, same-origin bootstrap. No authentication or app-frame state. */
(function () {
  var key = 'f01.theme.v1', media = window.matchMedia('(prefers-color-scheme: dark)');
  function valid(value) { return value === 'dark' || value === 'system' ? value : 'light'; }
  var preference = 'light';
  try { preference = valid(localStorage.getItem(key)); } catch (_) { /* Light is the new-user default. */ }
  function apply(value, save) {
    preference = valid(value);
    var theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.style.colorScheme = theme;
    if (save) { try { localStorage.setItem(key, preference); } catch (_) { /* Keep the in-page preference. */ } }
    window.dispatchEvent(new Event('f01-theme-changed'));
  }
  window.f01Theme = { get: function () { return preference; }, set: function (value) { apply(value, true); } };
  media.addEventListener('change', function () { if (preference === 'system') apply(preference, false); });
  window.addEventListener('storage', function (event) { if (event.key === key || event.key === null) apply(event.newValue, false); });
  apply(preference, false);
}());
