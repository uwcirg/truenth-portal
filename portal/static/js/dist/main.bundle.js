!function(t){var e={};function n(o){if(e[o])return e[o].exports;var i=e[o]={i:o,l:!1,exports:{}};return t[o].call(i.exports,i,i.exports,n),i.l=!0,i.exports}n.m=t,n.c=e,n.d=function(t,e,o){n.o(t,e)||Object.defineProperty(t,e,{enumerable:!0,get:o})},n.r=function(t){"undefined"!=typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(t,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(t,"__esModule",{value:!0})},n.t=function(t,e){if(1&e&&(t=n(t)),8&e)return t;if(4&e&&"object"==typeof t&&t&&t.__esModule)return t;var o=Object.create(null);if(n.r(o),Object.defineProperty(o,"default",{enumerable:!0,value:t}),2&e&&"string"!=typeof t)for(var i in t)n.d(o,i,function(e){return t[e]}.bind(null,i));return o},n.n=function(t){var e=t&&t.__esModule?function(){return t.default}:function(){return t};return n.d(e,"a",e),e},n.o=function(t,e){return Object.prototype.hasOwnProperty.call(t,e)},n.p="",n(n.s=26)}({1:function(t,e,n){"use strict";n.d(e,"b",function(){return r}),n.d(e,"c",function(){return a});var o,i=((o=function(){this.requestAttempts=0}).prototype.hasValue=function(t){return"null"!==String(t)&&""!==String(t)&&"undefined"!==String(t)},o.prototype.showMain=function(){$("#mainHolder").css({visibility:"visible","-ms-filter":"progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",filter:"alpha(opacity=100)","-moz-opacity":1,"-khtml-opacity":1,opacity:1})},o.prototype.hideLoader=function(t,e){t?$("#loadingIndicator").hide():setTimeout(function(){$("#loadingIndicator").fadeOut()},e||200)},o.prototype.loader=function(t){if(document.getElementById("fullSizeContainer"))return this.hideLoader(),this.showMain(),!1;if(t)$("#loadingIndicator").show();else if(!this.isDelayLoading()){var e=this;setTimeout(function(){e.showMain()},100),this.hideLoader(!0,350)}},o.prototype.isDelayLoading=function(){return"undefined"!=typeof DELAY_LOADING&&DELAY_LOADING},o.prototype.isTouchDevice=function(){return!0===("ontouchstart"in window||window.DocumentTouch&&document instanceof window.DocumentTouch)},o.prototype.getIEVersion=function(){var t=navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);return!!t&&parseInt(t[1])},o.prototype.newHttpRequest=function(t,e,n){this.requestAttempts++;var o,i=this;for(var r in n=n||function(){},window.XDomainRequest?(o=new XDomainRequest).onload=function(){n(o.responseText)}:o=window.XMLHttpRequest?new XMLHttpRequest:new ActiveXObject("Microsoft.XMLHTTP"),o.onreadystatechange=function(){if(4===o.readyState){if(200===o.status)return n(o.responseText),void(i.requestAttempts=0);i.requestAttempts<3?setTimeout(function(){i.newHttpRequest(t,e,n)},3e3):(n({error:o.responseText}),i.loader(),i.requestAttempts=0)}},e=e||{},o.open("GET",t,!0),e)e.hasOwnProperty(r)&&o.setRequestHeader(r,e[r]);e.cache||(o.setRequestHeader("cache-control","no-cache"),o.setRequestHeader("expires","-1"),o.setRequestHeader("pragma","no-cache")),o.send()},o.prototype.ajaxRequest=function(t,e,n){if(n=n||function(){},!t)return n({error:i18next.t("Url is required.")}),!1;var o={url:t,type:"GET",contentType:"text/plain",timeout:5e3,cache:!1};e=e||o,e=$.extend({},o,e),this.requestAttempts++;var i=this;$.ajax(e).done(function(t){n(t),i.requestAttempts=0}).fail(function(){i.requestAttempts<=3?setTimeout(function(){i.ajaxRequest(t,e,n)},3e3):(n({error:i18next.t("Error occurred processing request")}),i.requestAttempts=0,i.loader())}).always(function(){i.loader()})},o.prototype.initWorker=function(t,e,n){var o=new Worker("/static/js/ajaxWorker.js"),i=this;o.postMessage({url:t,params:e}),o.addEventListener("message",function(t){n.call(i,t.data),o.terminate()},!1),o.addEventListener("error",function(t){console.log("Worker runtime error: Line ",t.lineno," in ",t.filename,": ",t.message),o.terminate()},!1)},o.prototype.workerAllowed=function(){return window.Worker&&!this.isTouchDevice()},o.prototype.getRequestMethod=function(){return this.getIEVersion()?this.newHttpRequest:this.ajaxRequest},o.prototype.sendRequest=function(t,e,n){if((e=e||{}).useWorker&&this.workerAllowed())return this.initWorker(t,e,n),!0;this.getRequestMethod().call(this,t,e,function(t){n.call(this,t)})},o.prototype.LRKeyEvent=function(){$(".button--LR").length>0&&$("html").on("keydown",function(t){parseInt(t.keyCode)===parseInt(187)&&$(".button--LR").toggleClass("data-show")})},o.prototype.getLoaderHTML=function(t){return'<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i>'.concat(t?"&nbsp;"+t:"","</div>")},o.prototype.convertToNumericField=function(t){t&&this.isTouchDevice()&&t.each(function(){$(this).prop("type","tel")})},o.prototype.isString=function(t){return"[object String]"===Object.prototype.toString.call(t)},o.prototype.disableHeaderFooterLinks=function(){var t=$("#tnthNavWrapper a, #homeFooter a").not("a[href*='logout']").not("a.required-link").not("a.home-link");t.addClass("disabled"),t.prop("onclick",null).off("click"),t.on("click",function(t){return t.preventDefault(),!1})},o.prototype.pad=function(t){return t=parseInt(t),!isNaN(t)&&t<10?"0"+t:t},o.prototype.escapeHtml=function(t){return null===t||"undefined"!==t||0===String(t).length?t:t.replace(/[\"&'\/<>]/g,function(t){return{'"':"&quot;","&":"&amp;","'":"&#39;","/":"&#47;","<":"&lt;",">":"&gt;"}[t]})},o.prototype.containHtmlTags=function(t){return!!t&&/[<>]/.test(t)},o.prototype.getExportFileName=function(t){var e=new Date;return(t||"ExportList_")+("00"+e.getDate()).slice(-2)+("00"+(e.getMonth()+1)).slice(-2)+e.getFullYear()},o.prototype.capitalize=function(t){return t.replace(/\w\S*/g,function(t){return t.charAt(0).toUpperCase()+t.substr(1).toLowerCase()})},o.prototype.restoreVis=function(){var t=document.getElementById("loadingIndicator"),e=document.getElementById("mainHolder");t&&t.setAttribute("style","display:none; visibility:hidden;"),e&&e.setAttribute("style","visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1")},o.prototype.VueErrorHandling=function(){if("undefined"==typeof Vue)return!1;var t=this;Vue.config.errorHandler=function(e,n,o){var i,r=n;if(n.$options.errorHandler)i=n.$options.errorHandler;else for(;!i&&r.$parent;)i=(r=r.$parent).$options.errorHandler;t.restoreVis(),i?i.call(r,e,n,o):console.log(e)}},o.prototype.extend=function(t,e){for(var n in e)e.hasOwnProperty(n)&&(t[n]=e[n]);return t},o.prototype.getUrlParameter=function(t){t=t.replace(/[\[]/,"\\[").replace(/[\]]/,"\\]");var e=new RegExp("[\\?&]"+t+"=([^&#]*)").exec(location.search);return null===e?"":decodeURIComponent(e[1])},o.prototype.resetBrowserBackHistory=function(t,e,n){var o="undefined"!=typeof history&&history.pushState;t=t||location.href,o&&history.pushState(e,n,t),window.addEventListener("popstate",function(){o?history.pushState(e,n,t):window.history.forward(1)})},o.prototype.handlePostLogout=function(){if("undefined"==typeof sessionStorage)return!1;sessionStorage.getItem("logout")&&(this.resetBrowserBackHistory(location.orgin,"logout"),sessionStorage.removeItem("logout"))},o.prototype.displaySystemOutageMessage=function(t){if(t=(t=t||"en-us").replace("_","-"),document.getElementById("systemMaintenanceContainer")){var e=this;this.ajaxRequest("api/settings",{contentType:"application/json; charset=utf-8"},function(n){if(!n||!n.MAINTENANCE_MESSAGE&&!n.MAINTENANCE_WINDOW)return!1;var o=document.querySelector(".message-container");if(o||((o=document.createElement("div")).classList.add("message-container"),document.getElementById("systemMaintenanceContainer").appendChild(o)),n.MAINTENANCE_MESSAGE)o.innerHTML=e.escapeHtml(n.MAINTENANCE_MESSAGE);else if(n.MAINTENANCE_WINDOW&&n.MAINTENANCE_WINDOW.length){var i,r,a=new Date(n.MAINTENANCE_WINDOW[0]),s=new Date(n.MAINTENANCE_WINDOW[1]),c=(i=new Date,r=a,i&&r?Math.floor((r.getTime()-i.getTime())/36e5%24):0);if(c<0||isNaN(c))document.getElementById("systemMaintenanceContainer").classList.add("tnth-hide");else try{var u={year:"numeric",month:"long",day:"numeric",hour:"numeric",minute:"numeric",second:"numeric",hour12:!0,timeZoneName:"short"},l=a.toLocaleString(t,u).replace(/[,]/g," "),d=s.toLocaleString(t,u).replace(/[,]/g," "),f=["<div>"+i18next.t("Hi there.")+"</div>","<div>"+i18next.t("TrueNTH will be down for website maintenance starting <b>{startdate}</b>. This should last until <b>{enddate}</b>.".replace("{startdate}",l).replace("{enddate}",d))+"</div>","<div>"+i18next.t("Thanks for your patience while we upgrade our site.")+"</div>"].join("");o.innerHTML=e.escapeHtml(f)}catch(t){console.log("Error occurred converting system outage date/time ",t),document.getElementById("systemMaintenanceContainer").classList.add("tnth-hide")}}})}},new o);e.a=i;var r=i.getExportFileName,a=i.getUrlParameter},26:function(t,e,n){"use strict";n.r(e);var o=n(8),i=n(1),r={init:function(){this.registerModules(),this.setCustomJQueryEvents(this.checkJQuery()?jQuery||$:null),this.consolePolyFill()},registerModules:function(){"undefined"==typeof i18next&&(i18next={t:function(t){return t}}),window.portalModules||(window.portalModules={}),"undefined"!=typeof i18next&&(window.portalModules.i18next=i18next),window.portalModules.Global=this},checkJQuery:function(){return"undefined"!=typeof jQuery||(this.restoreVis(),!1)},handlePostLogout:function(){document.querySelector("body.landing")&&i.a.handlePostLogout()},handleClientInterventionForm:function(){document.querySelector("#clientAppForm")&&($("#confirmDel").popover({html:!0,content:"Are you sure you want to delete this app?<br /><br /><button type='submit' name='delete' value='delete' class='btn-tnth-primary btn'>Delete Now</button> &nbsp; <div class='btn btn-default' id='cancelDel'>Cancel</div>"}),$("body").on("click","#cancelDel",function(){$("#confirmDel").popover("hide")}))},onPageDidLoad:function(t){i.a.displaySystemOutageMessage(t),this.handlePostLogout(),this.showAlert(),this.handleNumericFields();var e=document.getElementById("LREditUrl");e&&this.appendLREditContainer(document.querySelector("#mainHolder .LREditContainer"),e.value,e.getAttribute("data-show")),this.prePopulateEmail(),this.beforeSendAjax(),this.unloadEvent(),this.footer(),this.loginAs(),this.initValidator(),this.handleClientInterventionForm()},prePopulateEmail:function(){var t=i.a.getUrlParameter("email"),e=document.querySelector("#email");t&&e&&(e.value=t)},handleDisableLinks:function(){i.a.getUrlParameter("disableLinks")&&i.a.disableHeaderFooterLinks()},beforeSendAjax:function(){$.ajaxSetup({beforeSend:function(t,e){/^(GET|HEAD|OPTIONS|TRACE)$/i.test(e.type)||this.crossDomain||t.setRequestHeader("X-CSRFToken",$("#__CRSF_TOKEN").val())}})},showAlert:function(){$("#alertModal").length>0&&$("#alertModal").modal("show")},restoreVis:function(){var t=document.getElementById("loadingIndicator"),e=document.getElementById("mainHolder");t&&t.setAttribute("style","display:none; visibility:hidden;"),e&&e.setAttribute("style","visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1")},showLoader:function(){document.querySelector("#loadingIndicator").setAttribute("style","display:block; visibility:visible;")},embedPortalWrapperContent:function(t){t&&!t.error&&$("#mainNav").html(t)},initPortalWrapper:function(t,e){var n=this;e=e||function(){},this.showLoader(),i.a.sendRequest(t,{cache:!1},function(t){if(!t||t.error)return document.querySelector("#mainNavLoadingError").innerHTML=i18next.t("Error loading portal wrapper"),n.restoreVis(),e(),!1;n.embedPortalWrapperContent(t),setTimeout(function(){n.restoreVis(),$("#tnthNavWrapper .logout").on("click",function(t){t.stopImmediatePropagation(),n.handleLogout()}),n.handleDisableLinks()},150),n.getNotification(function(t){n.notifications(t)}),e()})},loginAs:function(){if(!("undefined"!=typeof sessionStorage?sessionStorage.getItem("loginAsPatient"):null))return!1;this.clearSessionLocale(),this.getUserLocale(),i.a.resetBrowserBackHistory()},handleLogout:function(){sessionStorage.clear(),sessionStorage.setItem("logout","true")},unloadEvent:function(){var t=this;$(window).on("beforeunload",function(){i.a.getUrlParameter("logout")&&t.handleLogout()})},localeSessionKey:"currentUserLocale",clearSessionLocale:function(){sessionStorage.removeItem(this.localeSessionKey)},appendLREditContainer:function(t,e,n){return!!e&&(!!t&&($(t).append('<div><button class="btn btn-default button--LR"><a href="'.concat(e,'" target="_blank">').concat(i18next.t("Edit in Liferay"),"</a></button></div>")),void("true"===String(n).toLowerCase()?$(".button--LR").addClass("data-show"):$(".button--LR").addClass("tnth-hide"))))},getUserLocale:function(){var t=this.localeSessionKey,e=sessionStorage.getItem(t),n=document.querySelector("#userSessionLocale"),o=n?n.value:"";if(o)return sessionStorage.setItem(t,o),o;if(e)return e;if(!this.checkJQuery())return!1;var i="en_us";return $.ajax({type:"GET",url:"/api/me",async:!1}).done(function(e){var n="";if(e&&(n=e.id),!n)return i="en_us",!1;$.ajax({type:"GET",url:"/api/demographics/"+n,async:!1}).done(function(e){if(!e||!e.communication)return i="en_us",!1;e.communication.forEach(function(e){e.language&&(i=e.language.coding[0].code,sessionStorage.setItem(t,i))})})}).fail(function(){}),i},getCopyrightYear:function(t){t=t||function(){};var e=sessionStorage.getItem("config_COPYRIGHT_YEAR");e?t({configSuffix:e}):i.a.sendRequest("api/settings/COPYRIGHT_YEAR",!1,function(e){e&&e.hasOwnProperty("COPYRIGHT_YEAR")&&sessionStorage.setItem("config_COPYRIGHT_YEAR",e.COPYRIGHT_YEAR),t(e)})},footer:function(){var t=this,e=$("#homeFooter .logo-link");e.length>0&&e.each(function(){$.trim($(this).attr("href"))||($(this).removeAttr("target"),$(this).on("click",function(t){return t.preventDefault(),!1}))}),setTimeout(function(){$("#homeFooter").show()},100),setTimeout(function(){var e=t.getUserLocale(),n=$("#homeFooter .copyright"),o=(new Date).getFullYear();t.getCopyrightYear(function(t){t&&t.COPYRIGHT_YEAR&&(o=t.COPYRIGHT_YEAR);var i=function(t,e){var n="";switch(String(t.toUpperCase())){case"US":n=i18next.t("&copy; ".concat(e," Movember Foundation. All rights reserved. A registered 501(c)3 non-profit organization (Movember Foundation)."));break;case"AU":n=i18next.t("&copy; ".concat(e," Movember Foundation. All rights reserved. Movember Foundation is a registered charity in Australia ABN 48894537905 (Movember Foundation)."));break;case"NZ":n=i18next.t("&copy; ".concat(e," Movember Foundation. All rights reserved. Movember Foundation is a New Zealand registered charity number CC51320 (Movember Foundation)."));break;default:n=i18next.t("&copy; ".concat(e," Movember Foundation (Movember Foundation). All rights reserved."))}return n},r=e.split("_")[1];"EN_US"!==e.toUpperCase()?n.html(i(r,o)):$.getJSON("//geoip.cirg.washington.edu/json/",function(t){t&&t.country_code?n.html(i(t.country_code,o)):n.html(i(r,o))})})},500)},getNotification:function(t){var e=$("#notificationUserId").val();if(t=t||function(){},!e)return t({error:i18next.t("User id is required")}),!1;$.ajax({type:"GET",url:"/api/user/"+e+"/notification"}).done(function(e){t(e||{error:i18next.t("no data returned")})}).fail(function(){t({error:i18next.t("Error occurred retrieving notification.")})})},deleteNotification:function(t,e){if(!t||parseInt(e)<0||!e)return!1;var n=this;this.getNotification(function(t){if(t.notifications&&t.notifications.length){var o=$.grep(t.notifications,function(t){return parseInt(t.id)===parseInt(e)}),i=$("#notificationUserId").val();o.length&&$.ajax({type:"DELETE",url:"/api/user/"+i+"/notification/"+e}).done(function(){$("#notification_"+e).attr("data-visited",!0),$("#notification_"+e).find("[data-action-required]").removeAttr("data-action-required"),n.setNotificationsDisplay()})}})},notifications:function(t){if(!t||!t.notifications||0===t.notifications.length)return $("#notificationBanner").hide(),!1;var e=t.notifications.map(function(t){return'<div class="notification" id="notification_'.concat(t.id,'" data-id="').concat(t.id,'" data-name="').concat(t.name,'">').concat(t.content,"</div>")}),n=this;$("#notificationBanner .content").html(e.join("")),$("#notificationBanner .notification").addClass("active"),$("#notificationBanner").show(),$("#notificationBanner [data-id] a").each(function(){$(this).on("click",function(t){t.stopPropagation();var e=$(this).closest(".notification");e.attr("data-visited","true"),n.deleteNotification($("#notificationUserId").val(),e.attr("data-id")),n.setNotificationsDisplay()})}),$("#notificationBanner .close").on("click",function(t){t.stopPropagation(),$("#notificationBanner [data-id]").each(function(){$(this).find("[data-action-required]").length>0||($(this).attr("data-visited",!0),n.deleteNotification($("#notificationUserId").val(),$(this).attr("data-id")))}),n.setNotificationsDisplay()}),n.setNotificationsDisplay()},setNotificationsDisplay:function(){if($("#notificationBanner [data-action-required]").length>0)return $("#notificationBanner .close").removeClass("active"),!1;var t=!0;$("#notificationBanner [data-id]").each(function(){if(t&&!$(this).attr("data-visited"))return t=!1,!1}),t?$("#notificationBanner").hide():$("#notificationBanner .close").addClass("active")},setCustomJQueryEvents:function(t){if(!t)return!1;var e=t(window).height();t.fn.isOnScreen=function(){var n={};n.top=t(window).scrollTop(),n.bottom=n.top+e;var o={};return o.top=this&&this.offset()?this.offset().top:0,o.bottom=o.top+this.outerHeight(),o.top<=n.bottom&&o.bottom>=n.top},t.fn.sortOptions=function(){var e=t(this).find("option");return e.sort(function(t,e){return t.text>e.text?1:t.text<e.text?-1:0}),e}},consolePolyFill:function(){var t=window.console=window.console||{},e=function(){},n=t.log||e,o=function(t){return function(e){n("Start "+t+": "+e)}},i=function(t){return function(e){n("End "+t+": "+e)}},r={assert:e,clear:e,trace:e,count:e,timeStamp:e,msIsIndependentlyComposed:e,debug:n,info:n,log:n,warn:n,error:n,dir:n,dirxml:n,markTimeline:n,group:o("group"),groupCollapsed:o("groupCollapsed"),groupEnd:i("group"),profile:o("profile"),profileEnd:i("profile"),time:o("time"),timeEnd:i("time")};for(var a in r)!r.hasOwnProperty(a)||a in t||(t[a]=r[a])},handleNumericFields:function(){i.a.isTouchDevice()&&i.a.convertToNumericField($("#date, #year"))},initValidator:function(){if(void 0===$.fn.validator)return!1;$("form.to-validate").validator({custom:{birthday:function(){var t=parseInt($("#month").val()),e=parseInt($("#date").val()),n=parseInt($("#year").val()),o=!0,i="";return isNaN(n)||isNaN(e)&&isNaN(n)?($("#errorbirthday").html(i18next.t("All fields must be complete.")).hide(),o=!1):isNaN(e)?i=i18next.t("Please enter a valid date."):isNaN(t)?i+=(i?"<br/>":"")+i18next.t("Please enter a valid month."):isNaN(n)&&(i+=(i?"<br/>":"")+i18next.t("Please enter a valid year.")),i&&($("#errorbirthday").html(i).show(),$("#birthday").val(""),o=!1),o&&$("#errorbirthday").html("").hide(),o},customemail:function(t){var e=$.trim(t.val()),n=function(t){"true"===t.attr("data-update-on-validated")&&t.attr("data-user-id")&&t.trigger("postEventUpdate")};if(""===e)return!!t.attr("data-optional")&&(n(t),!0);var o=/^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/,r="";if(t.attr("data-user-id")&&(r="&user_id="+t.attr("data-user-id")),o.test(e)){var a="/api/unique_email?email="+encodeURIComponent(e)+r;i.a.sendRequest(a,{max_attempts:1},function(e){if(!e.error)return e.unique?($("#erroremail").html("").parents(".form-group").removeClass("has-error"),void n(t)):void $("#erroremail").html(i18next.t("This e-mail address is already in use. Please enter a different address.")).parents(".form-group").addClass("has-error");$("#erroremail").html(i18next.t("Error occurred when verifying the uniqueness of email")).parents(".form-group").addClass("has-error")})}return o.test(e)},htmltags:function(t){var e,n=!!(e=t.val())&&/[<>]/.test(e);return n?($("#error"+t.attr("id")).html("Invalid characters in text."),!1):($("#error"+t.attr("id")).html(""),!n)}},errors:{htmltags:i18next.t("Please remove invalid characters and try again."),birthday:i18next.t("Sorry, this isn't a valid date. Please try again."),customemail:i18next.t("This isn't a valid e-mail address, please double-check.")},disable:!1}).off("input.bs.validator change.bs.validator")}},a=r.getUserLocale();o.a.init({lng:a},function(){if(!r.checkJQuery())return alert("JQuery library necessary for this website was not loaded.  Please refresh your browser and try again."),!1;r.init(),$(document).ready(function(){r.initPortalWrapper(window.location.protocol+"//"+window.location.host+"/api/portal-wrapper-html/"),r.onPageDidLoad(a)})})},8:function(t,e,n){"use strict";e.a=function(){return{init:function(t,e){e=e||function(){};try{!function(t,e){var n=function(t){if(""===String(t))return{};for(var e={},n=0;n<t.length;++n){var o=t[n].split("=",2);1===o.length?e[o[0]]="":e[o[0]]=decodeURIComponent(o[1].replace(/\+/g," "))}return e}(window.location.search.substr(1).split("&"));void 0!==window.localStorage&&window.localStorage.getItem("i18nextLng")&&window.localStorage.removeItem("i18nextLng");var o=t.loadPath||"/static/files/locales/{{lng}}/translation.json",i={fallbackLng:"en-US",lng:"en-US",preload:!1,debug:!1,defaultNS:"translation",initImmediate:!1,keySeparator:"----",nsSeparator:"----",load:"currentOnly",returnEmptyString:!1,returnNull:!1,saveMissing:!1,missingKeyHandler:!1,parseMissingKeyHandler:function(t){var e=sessionStorage.getItem("i18nextData_"+this.lng);if(!e)return t;try{var n=JSON.parse(e);if(n&&n.hasOwnProperty(t))return n[t]}catch(e){return t}return t},backend:{language:t.lng,loadPath:o,ajax:function(t,e,n,o,i){n=n||function(){};var r,a="i18nextData_"+e.language;o&&"object"===(void 0===o?"undefined":_typeof(o))&&(i||(o._t=new Date),o=addQueryString("",o).slice(1)),e.queryStringParams&&(t=addQueryString(t,e.queryStringParams)),r=XMLHttpRequest?new XMLHttpRequest:new ActiveXObject("MSXML2.XMLHTTP.3.0");try{r.open(o?"POST":"GET",t,0),e.crossDomain||r.setRequestHeader("X-Requested-With","XMLHttpRequest"),r.withCredentials=!!e.withCredentials,o&&r.setRequestHeader("Content-type","application/x-www-form-urlencoded"),r.overrideMimeType&&r.overrideMimeType("application/json");var s=e.customHeaders;if(s)for(var c in s)s.hasOwnProperty(c)&&r.setRequestHeader(c,s[c]);r.onreadystatechange=function(){r.readyState>3&&(n(r.responseText,r),r.responseText&&!sessionStorage.getItem(a)&&sessionStorage.setItem(a,JSON.stringify(r.responseText)))},r.send(o)}catch(t){console&&console.log(t)}}}};(t=t||i).lng&&(t.lng=t.lng.replace("_","-")),t.debug=t.debug?t.debug:!!n.debugi18next;var r=i;for(var a in t)i.hasOwnProperty(a)&&(i[a]=t[a]);var s="i18nextData_"+t.language;if(e=e||function(){},"undefined"==typeof i18next)return e(),!1;"en-us"===String(t.lng).toLowerCase()||sessionStorage.getItem(s)?i18next.init(r,function(t,n){e(n)}):i18next.use(i18nextXHRBackend).init(r,function(t,n){e(n)})}(t,e)}catch(t){console.log("Error initialized i18next ",t.message),e()}}}}()}});
//# sourceMappingURL=../../maps/main.bundle.js.map