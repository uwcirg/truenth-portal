$(document).ready(function() {
    Utility.handlePostLogout(); /*global Utility handlePostLogout */
    if (typeof sessionStorage !== "undefined") {
        sessionStorage.clear();
    }
});

