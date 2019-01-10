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
/******/ 	return __webpack_require__(__webpack_require__.s = "./static/js/src/scheduledJobs.js");
/******/ })
/************************************************************************/
/******/ ({

/***/ "./static/js/src/scheduledJobs.js":
/*!****************************************!*\
  !*** ./static/js/src/scheduledJobs.js ***!
  \****************************************/
/*! no static exports found */
/***/ (function(module, exports) {

eval("$(document).ready(function () {\n  $(\"#scheduledJobsList .btn-toggle-job\").on(\"click\", function (event) {\n    /* global $ */\n    event.stopPropagation();\n    var jobId = $(this).attr(\"data-jobid\");\n\n    if (!jobId) {\n      return;\n    }\n\n    var current_job = \"#job_\" + jobId;\n    var current_text = \"#activeText_\" + jobId;\n    var current_icon = \"#activeIcon_\" + jobId;\n    var current_status = \"#lastStatus_\" + jobId;\n    var jobData = {\n      active: $(current_text).text() !== \"Active\"\n    };\n    $(current_job).children().prop(\"disabled\", true);\n    $(current_job).fadeTo(\"fast\", .6);\n    $.ajax({\n      type: \"PUT\",\n      url: \"/api/scheduled_job/\" + jobId,\n      contentType: \"application/json; charset=utf-8\",\n      dataType: \"json\",\n      data: JSON.stringify(jobData)\n    }).done(function (data) {\n      if (data) {\n        if (data[\"active\"]) {\n          $(current_text).text(\"Active\");\n          $(current_text).removeClass(\"text-danger\");\n          $(current_icon).removeClass(\"fa fa-toggle-off\");\n          $(current_text).addClass(\"text-info\");\n          $(current_icon).addClass(\"fa fa-toggle-on\");\n        } else {\n          $(current_text).text(\"Inactive\");\n          $(current_text).removeClass(\"text-info\");\n          $(current_icon).removeClass(\"fa fa-toggle-on\");\n          $(current_text).addClass(\"text-danger\");\n          $(current_icon).addClass(\"fa fa-toggle-off\");\n        }\n\n        $(current_job).fadeTo(\"fast\", 1);\n        $(current_job).children().prop(\"disabled\", false);\n      } else {\n        $(current_status).text(\"No response received\");\n        $(current_status).removeClass(\"text-info\");\n        $(current_status).addClass(\"text-danger\");\n      }\n    }).fail(function (xhr) {\n      console.log(\"response Text: \" + xhr.responseText);\n      console.log(\"response status: \" + xhr.status);\n      $(current_status).text(xhr.status + \": \" + xhr.responseText);\n      $(current_status).removeClass(\"text-info\");\n      $(current_status).addClass(\"text-danger\");\n    });\n  });\n  $(\"#scheduledJobsList .btn-run-job\").on(\"click\", function (event) {\n    event.stopPropagation();\n    var jobId = $(this).attr(\"data-jobid\");\n\n    if (!jobId) {\n      return;\n    }\n\n    var current_job = \"#job_\" + jobId;\n    var current_status = \"#lastStatus_\" + jobId;\n    var current_runtime = \"#lastRuntime_\" + jobId;\n    $(current_job).children().prop(\"disabled\", true);\n    $(current_job).fadeTo(\"fast\", .6);\n    $.ajax({\n      type: \"POST\",\n      url: \"/api/scheduled_job/\" + jobId + \"/trigger\",\n      contentType: \"application/json; charset=utf-8\",\n      dataType: \"json\"\n    }).done(function (data) {\n      if (data) {\n        $(current_status).text(data[\"message\"]);\n        $(current_runtime).text(data[\"runtime\"]);\n        $(current_job).fadeTo(\"fast\", 1);\n        $(current_job).children().prop(\"disabled\", false);\n      } else {\n        $(current_status).text(\"No response received\");\n        $(current_status).removeClass(\"text-info\");\n        $(current_status).addClass(\"text-danger\");\n      }\n    }).fail(function (xhr) {\n      /*eslint no-console: off*/\n      console.log(\"response Text: \" + xhr.responseText);\n      console.log(\"response status: \" + xhr.status);\n      $(current_status).text(xhr.status + \": \" + xhr.responseText);\n      $(current_status).removeClass(\"text-info\");\n      $(current_status).addClass(\"text-danger\");\n    });\n  });\n});\n\n//# sourceURL=webpack:///./static/js/src/scheduledJobs.js?");

/***/ })

/******/ });
//# sourceMappingURL=../../maps/scheduledJobs.bundle.js.map