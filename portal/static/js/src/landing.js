import Utility from "./modules/Utility.js";
$(document).ready(function() {
    Utility.handlePostLogout(); /*global Utility handlePostLogout */
    if (typeof sessionStorage !== "undefined") {
        sessionStorage.clear();
    }
});


