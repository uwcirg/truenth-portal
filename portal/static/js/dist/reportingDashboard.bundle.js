/******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};
/******/
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/
/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId]) {
/******/ 			return installedModules[moduleId].exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			i: moduleId,
/******/ 			l: false,
/******/ 			exports: {}
/******/ 		};
/******/
/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/
/******/ 		// Flag the module as loaded
/******/ 		module.l = true;
/******/
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/
/******/
/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;
/******/
/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;
/******/
/******/ 	// define getter function for harmony exports
/******/ 	__webpack_require__.d = function(exports, name, getter) {
/******/ 		if(!__webpack_require__.o(exports, name)) {
/******/ 			Object.defineProperty(exports, name, { enumerable: true, get: getter });
/******/ 		}
/******/ 	};
/******/
/******/ 	// define __esModule on exports
/******/ 	__webpack_require__.r = function(exports) {
/******/ 		if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/ 			Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 		}
/******/ 		Object.defineProperty(exports, '__esModule', { value: true });
/******/ 	};
/******/
/******/ 	// create a fake namespace object
/******/ 	// mode & 1: value is a module id, require it
/******/ 	// mode & 2: merge all properties of value into the ns
/******/ 	// mode & 4: return value when already ns object
/******/ 	// mode & 8|1: behave like require
/******/ 	__webpack_require__.t = function(value, mode) {
/******/ 		if(mode & 1) value = __webpack_require__(value);
/******/ 		if(mode & 8) return value;
/******/ 		if((mode & 4) && typeof value === 'object' && value && value.__esModule) return value;
/******/ 		var ns = Object.create(null);
/******/ 		__webpack_require__.r(ns);
/******/ 		Object.defineProperty(ns, 'default', { enumerable: true, value: value });
/******/ 		if(mode & 2 && typeof value != 'string') for(var key in value) __webpack_require__.d(ns, key, function(key) { return value[key]; }.bind(null, key));
/******/ 		return ns;
/******/ 	};
/******/
/******/ 	// getDefaultExport function for compatibility with non-harmony modules
/******/ 	__webpack_require__.n = function(module) {
/******/ 		var getter = module && module.__esModule ?
/******/ 			function getDefault() { return module['default']; } :
/******/ 			function getModuleExports() { return module; };
/******/ 		__webpack_require__.d(getter, 'a', getter);
/******/ 		return getter;
/******/ 	};
/******/
/******/ 	// Object.prototype.hasOwnProperty.call
/******/ 	__webpack_require__.o = function(object, property) { return Object.prototype.hasOwnProperty.call(object, property); };
/******/
/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "";
/******/
/******/
/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(__webpack_require__.s = "./static/js/src/reportingDashboard.js");
/******/ })
/************************************************************************/
/******/ ({

/***/ "./static/js/src/modules/Utility.js":
/*!******************************************!*\
  !*** ./static/js/src/modules/Utility.js ***!
  \******************************************/
/*! exports provided: default, getExportFileName, getUrlParameter */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, \"getExportFileName\", function() { return getExportFileName; });\n/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, \"getUrlParameter\", function() { return getUrlParameter; });\nvar Utility = function () {\n  var UtilityObj = function UtilityObj() {\n    /*global $ */\n    this.requestAttempts = 0;\n  };\n\n  UtilityObj.prototype.hasValue = function (val) {\n    return String(val) !== \"null\" && String(val) !== \"\" && String(val) !== \"undefined\";\n  };\n\n  UtilityObj.prototype.showMain = function () {\n    $(\"#mainHolder\").css({\n      \"visibility\": \"visible\",\n      \"-ms-filter\": \"progid:DXImageTransform.Microsoft.Alpha(Opacity=100)\",\n      \"filter\": \"alpha(opacity=100)\",\n      \"-moz-opacity\": 1,\n      \"-khtml-opacity\": 1,\n      \"opacity\": 1\n    });\n  };\n\n  UtilityObj.prototype.hideLoader = function (delay, time) {\n    if (delay) {\n      $(\"#loadingIndicator\").hide();\n      return;\n    }\n\n    setTimeout(function () {\n      $(\"#loadingIndicator\").fadeOut();\n    }, time || 200);\n  };\n\n  UtilityObj.prototype.loader = function (show) {\n    //landing page\n    if (document.getElementById(\"fullSizeContainer\")) {\n      this.hideLoader();\n      this.showMain();\n      return false;\n    }\n\n    if (show) {\n      $(\"#loadingIndicator\").show();\n      return;\n    }\n\n    if (!this.isDelayLoading()) {\n      var self = this;\n      setTimeout(function () {\n        self.showMain();\n      }, 100);\n      this.hideLoader(true, 350);\n    }\n  };\n\n  UtilityObj.prototype.isDelayLoading = function () {\n    /*global DELAY_LOADING*/\n    return typeof DELAY_LOADING !== \"undefined\" && DELAY_LOADING;\n  };\n\n  UtilityObj.prototype.isTouchDevice = function () {\n    return true === (\"ontouchstart\" in window || window.DocumentTouch && document instanceof window.DocumentTouch);\n  };\n\n  UtilityObj.prototype.getIEVersion = function () {\n    var match = navigator.userAgent.match(/(?:MSIE |Trident\\/.*; rv:)(\\d+)/);\n    return match ? parseInt(match[1]) : false;\n  };\n\n  UtilityObj.prototype.newHttpRequest = function (url, params, callBack) {\n    /* note: this function supports older version of IE (version <= 9) - jquery ajax calls errored in older IE version*/\n    this.requestAttempts++;\n    var xmlhttp,\n        self = this;\n\n    callBack = callBack || function () {};\n\n    if (window.XDomainRequest) {\n      /*global XDomainRequest */\n      xmlhttp = new XDomainRequest();\n\n      xmlhttp.onload = function () {\n        callBack(xmlhttp.responseText);\n      };\n    } else if (window.XMLHttpRequest) {\n      xmlhttp = new XMLHttpRequest();\n    } else {\n      xmlhttp = new ActiveXObject(\"Microsoft.XMLHTTP\");\n      /*global ActiveXObject */\n    }\n\n    xmlhttp.onreadystatechange = function () {\n      if (xmlhttp.readyState === 4) {\n        if (xmlhttp.status === 200) {\n          callBack(xmlhttp.responseText);\n          self.requestAttempts = 0;\n          return;\n        }\n\n        if (self.requestAttempts < 3) {\n          setTimeout(function () {\n            self.newHttpRequest(url, params, callBack);\n          }, 3000);\n        } else {\n          callBack({\n            error: xmlhttp.responseText\n          });\n          self.loader();\n          self.requestAttempts = 0;\n        }\n      }\n    };\n\n    params = params || {};\n    xmlhttp.open(\"GET\", url, true);\n\n    for (var param in params) {\n      if (params.hasOwnProperty(param)) {\n        xmlhttp.setRequestHeader(param, params[param]);\n      }\n    }\n\n    if (!params.cache) {\n      xmlhttp.setRequestHeader(\"cache-control\", \"no-cache\");\n      xmlhttp.setRequestHeader(\"expires\", \"-1\");\n      xmlhttp.setRequestHeader(\"pragma\", \"no-cache\"); //legacy HTTP 1.0 servers and IE support\n    }\n\n    xmlhttp.send();\n  };\n\n  UtilityObj.prototype.ajaxRequest = function (url, params, callback) {\n    callback = callback || function () {};\n\n    if (!url) {\n      callback({\n        error: i18next.t(\"Url is required.\")\n      });\n      return false;\n    }\n\n    var defaults = {\n      url: url,\n      type: \"GET\",\n      contentType: \"text/plain\",\n      timeout: 5000,\n      cache: false\n    };\n    params = params || defaults;\n    params = $.extend({}, defaults, params);\n    this.requestAttempts++;\n    var uself = this;\n    $.ajax(params).done(function (data) {\n      callback(data);\n      uself.requestAttempts = 0;\n    }).fail(function () {\n      if (uself.requestAttempts <= 3) {\n        setTimeout(function () {\n          uself.ajaxRequest(url, params, callback);\n        }, 3000);\n      } else {\n        callback({\n          error: i18next.t(\"Error occurred processing request\")\n        });\n        /*global i18next */\n\n        uself.requestAttempts = 0;\n        uself.loader();\n      }\n    }).always(function () {\n      uself.loader();\n    });\n  };\n\n  UtilityObj.prototype.initWorker = function (url, params, callbackFunc) {\n    var worker = new Worker(\"/static/js/ajaxWorker.js\");\n    var self = this;\n    worker.postMessage({\n      url: url,\n      params: params\n    });\n    worker.addEventListener(\"message\", function (e) {\n      callbackFunc.call(self, e.data);\n      worker.terminate();\n    }, false);\n    worker.addEventListener(\"error\", function (e) {\n      console.log(\"Worker runtime error: Line \", e.lineno, \" in \", e.filename, \": \", e.message);\n      worker.terminate();\n    }, false);\n  };\n\n  UtilityObj.prototype.workerAllowed = function () {\n    return window.Worker && !this.isTouchDevice();\n  };\n\n  UtilityObj.prototype.getRequestMethod = function () {\n    return this.getIEVersion() ? this.newHttpRequest : this.ajaxRequest; //NOTE JQuery ajax request does not work for IE <= 9\n  };\n\n  UtilityObj.prototype.sendRequest = function (url, params, callback) {\n    /*generic function for sending GET ajax request, make use of worker if possible */\n    params = params || {};\n\n    if (params.useWorker && this.workerAllowed()) {\n      this.initWorker(url, params, callback);\n      return true;\n    }\n\n    var useFunc = this.getRequestMethod();\n    useFunc.call(this, url, params, function (data) {\n      callback.call(this, data);\n    });\n  };\n\n  UtilityObj.prototype.LRKeyEvent = function () {\n    var LR_INVOKE_KEYCODE = 187;\n\n    if ($(\".button--LR\").length > 0) {\n      $(\"html\").on(\"keydown\", function (e) {\n        if (parseInt(e.keyCode) === parseInt(LR_INVOKE_KEYCODE)) {\n          $(\".button--LR\").toggleClass(\"data-show\");\n        }\n      });\n    }\n  };\n\n  UtilityObj.prototype.getLoaderHTML = function (message) {\n    return \"<div class=\\\"loading-message-indicator\\\"><i class=\\\"fa fa-spinner fa-spin fa-2x\\\"></i>\".concat(message ? \"&nbsp;\" + message : \"\", \"</div>\");\n  };\n\n  UtilityObj.prototype.convertToNumericField = function (field) {\n    if (!field) {\n      return;\n    }\n\n    if (this.isTouchDevice()) {\n      field.each(function () {\n        $(this).prop(\"type\", \"tel\");\n      });\n    }\n  };\n\n  UtilityObj.prototype.isString = function (obj) {\n    return Object.prototype.toString.call(obj) === \"[object String]\";\n  };\n\n  UtilityObj.prototype.disableHeaderFooterLinks = function () {\n    var links = $(\"#tnthNavWrapper a, #homeFooter a\").not(\"a[href*='logout']\").not(\"a.required-link\").not(\"a.home-link\");\n    links.addClass(\"disabled\");\n    links.prop(\"onclick\", null).off(\"click\");\n    links.on(\"click\", function (e) {\n      e.preventDefault();\n      return false;\n    });\n  };\n\n  UtilityObj.prototype.pad = function (n) {\n    n = parseInt(n);\n    return !isNaN(n) && n < 10 ? \"0\" + n : n;\n  };\n\n  UtilityObj.prototype.escapeHtml = function (text) {\n    \"use strict\";\n\n    if (text === null || text !== \"undefined\" || String(text).length === 0) {\n      return text;\n    }\n\n    return text.replace(/[\\\"&'\\/<>]/g, function (a) {\n      return {\n        '\"': \"&quot;\",\n        \"&\": \"&amp;\",\n        \"'\": \"&#39;\",\n        \"/\": \"&#47;\",\n        \"<\": \"&lt;\",\n        \">\": \"&gt;\"\n      }[a];\n    });\n  };\n\n  UtilityObj.prototype.containHtmlTags = function (text) {\n    if (!text) {\n      return false;\n    }\n\n    return /[<>]/.test(text);\n  };\n\n  UtilityObj.prototype.getExportFileName = function (prefix) {\n    var d = new Date();\n    return (prefix ? prefix : \"ExportList_\") + (\"00\" + d.getDate()).slice(-2) + (\"00\" + (d.getMonth() + 1)).slice(-2) + d.getFullYear();\n  };\n\n  UtilityObj.prototype.capitalize = function (str) {\n    return str.replace(/\\w\\S*/g, function (txt) {\n      return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();\n    });\n  };\n\n  UtilityObj.prototype.restoreVis = function () {\n    var loadingElement = document.getElementById(\"loadingIndicator\"),\n        mainElement = document.getElementById(\"mainHolder\");\n\n    if (loadingElement) {\n      loadingElement.setAttribute(\"style\", \"display:none; visibility:hidden;\");\n    }\n\n    if (mainElement) {\n      mainElement.setAttribute(\"style\", \"visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1\");\n    }\n  };\n\n  UtilityObj.prototype.VueErrorHandling = function () {\n    if (typeof Vue === \"undefined\") {\n      return false;\n    }\n    /*global Vue */\n\n\n    var self = this;\n\n    Vue.config.errorHandler = function (err, vm, info) {\n      var handler,\n          current = vm;\n\n      if (vm.$options.errorHandler) {\n        handler = vm.$options.errorHandler;\n      } else {\n        while (!handler && current.$parent) {\n          current = current.$parent;\n          handler = current.$options.errorHandler;\n        }\n      }\n\n      self.restoreVis();\n\n      if (handler) {\n        handler.call(current, err, vm, info);\n        return;\n      }\n\n      console.log(err);\n    };\n  };\n\n  UtilityObj.prototype.extend = function (obj, extension) {\n    // Extend an object with an extension\n    for (var key in extension) {\n      if (extension.hasOwnProperty(key)) {\n        obj[key] = extension[key];\n      }\n    }\n\n    return obj;\n  };\n\n  UtilityObj.prototype.getUrlParameter = function (name) {\n    name = name.replace(/[\\[]/, \"\\\\[\").replace(/[\\]]/, \"\\\\]\");\n    var regex = new RegExp(\"[\\\\?&]\" + name + \"=([^&#]*)\");\n    var results = regex.exec(location.search);\n    return results === null ? \"\" : decodeURIComponent(results[1]);\n  };\n\n  UtilityObj.prototype.resetBrowserBackHistory = function (locationUrl, stateObject, title) {\n    var historyDefined = typeof history !== \"undefined\" && history.pushState;\n    locationUrl = locationUrl || location.href;\n\n    if (historyDefined) {\n      history.pushState(stateObject, title, locationUrl);\n    }\n\n    window.addEventListener(\"popstate\", function () {\n      if (historyDefined) {\n        history.pushState(stateObject, title, locationUrl);\n      } else {\n        window.history.forward(1);\n      }\n    });\n  };\n\n  UtilityObj.prototype.handlePostLogout = function () {\n    if (typeof sessionStorage === \"undefined\") {\n      return false;\n    }\n\n    if (sessionStorage.getItem(\"logout\")) {\n      this.resetBrowserBackHistory(location.orgin, \"logout\");\n      /* global resetBrowserBackHistory */\n\n      sessionStorage.removeItem(\"logout\");\n    }\n  };\n\n  UtilityObj.prototype.displaySystemOutageMessage = function (locale) {\n    locale = locale || \"en-us\";\n    locale = locale.replace(\"_\", \"-\");\n    var systemMaintenanceElId = \"systemMaintenanceContainer\";\n\n    if (!document.getElementById(systemMaintenanceElId)) {\n      //check for system outage maintenance message element\n      return;\n    }\n\n    var self = this;\n    this.ajaxRequest(\"api/settings\", {\n      contentType: \"application/json; charset=utf-8\"\n    }, function (data) {\n      if (!data || !(data.MAINTENANCE_MESSAGE || data.MAINTENANCE_WINDOW)) {\n        return false;\n      }\n\n      var messageElement = document.querySelector(\".message-container\");\n\n      if (!messageElement) {\n        messageElement = document.createElement(\"div\");\n        messageElement.classList.add(\"message-container\");\n        document.getElementById(systemMaintenanceElId).appendChild(messageElement);\n      }\n\n      if (data.MAINTENANCE_MESSAGE) {\n        messageElement.innerHTML = self.escapeHtml(data.MAINTENANCE_MESSAGE);\n        return;\n      }\n\n      if (!data.MAINTENANCE_WINDOW || !data.MAINTENANCE_WINDOW.length) {\n        return;\n      } //use maintenance window specified in config to compose the message, assuming in following example format: [\"2018-11-02T12:00:00Z\", \"2018-11-02T18:00:00Z\"], dates in system ISO format\n\n\n      var hoursDiff = function hoursDiff(d1, d2) {\n        if (!d1 || !d2) {\n          return 0;\n        }\n\n        return Math.floor((d2.getTime() - d1.getTime()) / (1000 * 60 * 60) % 24);\n      }; //date object automatically convert iso date/time to local date/time as it assumes a timezone of UTC if date in ISO format\n\n\n      var startDate = new Date(data.MAINTENANCE_WINDOW[0]),\n          endDate = new Date(data.MAINTENANCE_WINDOW[1]);\n      var hoursTil = hoursDiff(new Date(), startDate);\n\n      if (hoursTil < 0 || isNaN(hoursTil)) {\n        //maintenance window has passed\n        document.getElementById(systemMaintenanceElId).classList.add(\"tnth-hide\");\n        return;\n      }\n      /*global i18next */\n      //construct message based on maintenance window\n\n\n      try {\n        var options = {\n          year: \"numeric\",\n          month: \"long\",\n          day: \"numeric\",\n          hour: \"numeric\",\n          minute: \"numeric\",\n          second: \"numeric\",\n          hour12: true,\n          timeZoneName: \"short\"\n        };\n        var displayStartDate = startDate.toLocaleString(locale, options).replace(/[,]/g, \" \"); //display language-sensitive representation of date/time\n\n        var displayEndDate = endDate.toLocaleString(locale, options).replace(/[,]/g, \" \");\n        var message = [\"<div>\" + i18next.t(\"Hi there.\") + \"</div>\", \"<div>\" + i18next.t(\"TrueNTH will be down for website maintenance starting <b>{startdate}</b>. This should last until <b>{enddate}</b>.\".replace(\"{startdate}\", displayStartDate).replace(\"{enddate}\", displayEndDate)) + \"</div>\", \"<div>\" + i18next.t(\"Thanks for your patience while we upgrade our site.\") + \"</div>\"].join(\"\");\n        messageElement.innerHTML = self.escapeHtml(message);\n      } catch (e) {\n        console.log(\"Error occurred converting system outage date/time \", e);\n        /*eslint no-console:off */\n\n        document.getElementById(systemMaintenanceElId).classList.add(\"tnth-hide\");\n      }\n    });\n  };\n\n  return new UtilityObj();\n}();\n\n/* harmony default export */ __webpack_exports__[\"default\"] = (Utility);\nvar getExportFileName = Utility.getExportFileName;\n/* expose common functions */\n\nvar getUrlParameter = Utility.getUrlParameter;\n\n//# sourceURL=webpack:///./static/js/src/modules/Utility.js?");

/***/ }),

/***/ "./static/js/src/reportingDashboard.js":
/*!*********************************************!*\
  !*** ./static/js/src/reportingDashboard.js ***!
  \*********************************************/
/*! no exports provided */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
eval("__webpack_require__.r(__webpack_exports__);\n/* harmony import */ var _modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./modules/Utility.js */ \"./static/js/src/modules/Utility.js\");\n\n/*global $*/\n\n(function () {\n  /*\n  * initiate bootstrapTable for all stats table\n  */\n  $(\"#orgStatsTable\").bootstrapTable({\n    exportOptions: {\n      fileName: Object(_modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__[\"getExportFileName\"])(\"OrganizationList_\")\n    }\n  });\n  $(\"#usageStatsTable\").bootstrapTable({\n    exportOptions: {\n      fileName: Object(_modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__[\"getExportFileName\"])(\"UsageStatsList_\")\n    }\n  });\n  $(\"#userRoleStatsTable\").bootstrapTable({\n    exportOptions: {\n      fileName: Object(_modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__[\"getExportFileName\"])(\"UserByRoleStatsList_\")\n    }\n  });\n  $(\"#userIntervStatsTable\").bootstrapTable({\n    exportOptions: {\n      fileName: Object(_modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__[\"getExportFileName\"])(\"UserByInterventionStatsList_\")\n    }\n  });\n  $(\"#userPatientReportStatsTable\").bootstrapTable({\n    exportOptions: {\n      fileName: Object(_modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__[\"getExportFileName\"])(\"UserByPatientReportStatsList_\")\n    }\n  });\n  $(\"#userIntervAccessStatsTable\").bootstrapTable({\n    exportOptions: {\n      fileName: Object(_modules_Utility_js__WEBPACK_IMPORTED_MODULE_0__[\"getExportFileName\"])(\"UserByInterventionAccessStatsList_\")\n    }\n  });\n  $(\"document\").ready(function () {\n    /*\n    * the class active will allow content related to the selected tab/item to show\n    * the related item is found based on the data-id attributed attached to each anchor element\n    */\n    $(\"ul.nav li\").each(function () {\n      $(this).on(\"click\", function () {\n        $(\"ul.nav li\").removeClass(\"active\");\n        $(this).addClass(\"active\");\n        var containerID = $(this).find(\"a\").attr(\"data-id\");\n\n        if (containerID) {\n          $(\".stats-container\").removeClass(\"active\");\n          $(\"#\" + containerID + \"_container\").addClass(\"active\");\n        }\n      });\n    });\n    /*\n    * add placeholder text for select filter control\n    */\n\n    (function () {\n      function addFilterPlaceHolders() {\n        $(\".stats-table .filterControl select option[value='']\").text(\"Select\");\n      }\n\n      $(\".stats-table\").on(\"reset-view.bs.table\", function () {\n        addFilterPlaceHolders();\n      });\n      addFilterPlaceHolders();\n    })();\n  });\n})();\n\n//# sourceURL=webpack:///./static/js/src/reportingDashboard.js?");

/***/ })

/******/ });
//# sourceMappingURL=../../maps/reportingDashboard.bundle.js.map