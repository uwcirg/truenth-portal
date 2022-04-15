/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/
import __i18next from "./modules/I18nextConfig.js";
import Global from "./modules/Global.js";
/*global __i18next*/
var userSetLang = Global.getUserLocale();
__i18next.init({"lng": userSetLang
}, function() {
    if (!Global.checkJQuery()) { alert("JQuery library necessary for this website was not loaded. Please refresh your browser and try again."); return false; }
    Global.init();
    $(document).ready(function() {
        Global.initPortalWrapper(window.location.protocol + "//" + window.location.host + "/api/portal-wrapper-html/");
        Global.onPageDidLoad(userSetLang);
    });
});
