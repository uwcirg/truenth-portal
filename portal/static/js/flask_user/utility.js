function getRememberMeCookieName() {
  return "Truenth2FA_REMEMBERME";
}
function setRememberMeCookieValue() {
  var COOKIE_NAME = getRememberMeCookieName();
  var cookieValue = btoa(new Date().getTime()); //encode in base64
  setCookie(COOKIE_NAME, cookieValue, 14);
  return cookieValue;
}
function removeRememberMeCookie() {
  // delete existing
  setCookie(getRememberMeCookieName(), "", 0);
}
function getRememberMeCookieValue() {
  return getCookie(getRememberMeCookieName());
}
function getRememberMeInputId() {
  return "truenth_rememberme_cookie_value";
}
function initRememberMeInputField() {
  var cookieValue = getRememberMeCookieValue() || "";
  console.log("cookie value ", cookieValue);
  var rememberMeInputFieldName = getRememberMeInputId();
  if ($("[name='" + rememberMeInputFieldName + "]").length) {
    $("[name='" + rememberMeInputFieldName + "]").val(cookieValue);
    return;
  }
  $("form").append(
    '<input type="hidden" name="' +
      rememberMeInputFieldName +
      '" value="' +
      cookieValue +
      '" />'
  );
}
function setRememberMeInputValue() {
  $("[name='" + getRememberMeInputId() + "]").val(setRememberMeCookieValue());
}
function setCookie(name, value, daysToLive) {
  var encodedValue = encodeURIComponent(value);
  // Encode value in order to escape semicolons, commas, and whitespace
  var cookie = name + "=" + encodedValue;

  if (typeof daysToLive === "number") {
    /* Sets the expires attribute so that the cookie expires
        after the specified number of days */
    // Set a persistent cookie that expires in [daysToLive] days
    var expirationDate = new Date();
    expirationDate.setDate(expirationDate.getDate() + daysToLive);
    cookie += "; expires=" + expirationDate;
    cookie += "; path=/";
    document.cookie = cookie;
  }
}
function getCookie(name) {
  // Split cookie string and get all individual name=value pairs in an array
  var cookieArr = document.cookie.split(";");

  // Loop through the array elements
  for (var i = 0; i < cookieArr.length; i++) {
    var cookiePair = cookieArr[i].split("=");

    /* Removing whitespace at the beginning of the cookie name
        and compare it with the given string */
    if (name == cookiePair[0].trim()) {
      // Decode the cookie value and return
      return decodeURIComponent(cookiePair[1]);
    }
  }
  // Return null if not found
  return null;
}
