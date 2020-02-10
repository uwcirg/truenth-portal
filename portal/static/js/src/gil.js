import Utility from "./modules/Utility.js";
import tnthAjax from "./modules/TnthAjax.js";
import __i18next from "./modules/I18nextConfig.js";
$.ajaxSetup({
  beforeSend: function(xhr, settings) {
    if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
      xhr.setRequestHeader("X-CSRFToken", $("#csrfToken").val());
    }
  }
});

__i18next.init({"debug": false, "initImmediate": false});

var RETURN_KEY_CODE = 13;


(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);throw new Error("Cannot find module '"+o+"'")}var f=n[o]={exports:{}};t[o][0].call(f.exports,function(e){var n=t[o][1][e];return s(n?n:e)},f,f.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
module.exports = {
  fx: {
    easing: "easeOutExpo",
    speed: {
      slow: 1500,
      mid: 1000,
      fast: 1000
    }
  }
};


},{}],2:[function(require,module,exports){

var UpperBanner = require("./modules/upper-banner");

var WindowScroll = require("./modules/window-scroll");

var WindowResize = require("./modules/window-resize");

var NavToggle = require("./modules/nav-toggle");

var Global = require("./modules/global");

var Admin = require("./modules/admin");

var Video = require("./modules/video");

var VisObj = require("./modules/visobj");

var MenuObj = require("./modules/menuObj");

var InterventionSessionObj = require("./modules/interventionSessionObj");

var OrgTool = require("./modules/orgTool");

var AccessCodeObj= require("./modules/accessCodeObj");

var UtilObj = require("./modules/utilObj");


$(function() {
  if (window.app == null) {
    window.app = {};
  }
  window.app.global = new Global();
  window.app.upperBanner = new UpperBanner();
  window.app.windowScroll = new WindowScroll();
  window.app.windowResize = new WindowResize();
  window.app.navToggle = new NavToggle();
  window.app.admin = new Admin();
  window.app.visObj = new VisObj();
  window.app.interventionSessionObj = new InterventionSessionObj();
  window.app.orgTool = new OrgTool();
  window.app.menuObj = new MenuObj();
  window.app.video = new Video();
  window.app.accessCodeObj = new AccessCodeObj();
  window.app.utilObj = new UtilObj();
});


},{"./modules/admin":3,"./modules/global":4,"./modules/nav-toggle":5,"./modules/upper-banner":6,"./modules/video":7,"./modules/window-resize":8,"./modules/window-scroll":9, "./modules/visobj":10, "./modules/interventionSessionObj":11, "./modules/orgTool":12, "./modules/menuObj":13, "./modules/accessCodeObj":14, "./modules/utilObj":15}],3:[function(require,module,exports){
var Admin, loggedInAdminClass, loggedInClass, upperBannerClosedClass;

loggedInAdminClass = "is-showing-logged-in";

loggedInClass = "is-logged-in";

upperBannerClosedClass = "is-upper-banner-closed";

module.exports = Admin = (function() {
  function Admin() {
    this.build();
  }

  Admin.prototype.build = function() {
    return $(".js-mock-submit").on("submit", function(e) {
      e.preventDefault();
      return $(this).addClass("is-submitted");
    });
  };

  return Admin;

})();


},{}],4:[function(require,module,exports){
var Global, config;

config = require("../config");

module.exports = Global = (function() {
  function Global() {
    this.addFX();
    this.addPlugins();
    this.bindEvents();
    this.setRoles();
  }

  Global.prototype.addFX = function() {
    return $.extend($.easing, window.easing);
  };

  Global.prototype.addPlugins = function() {
    $(".modal").on("show.bs.modal", function(e) {
      return $(this).addClass("is-modal-active");
    });
    return $(".modal").on("hide.bs.modal", function(e) {
      var $this;
      $this = $(this);
      return setTimeout(function() {
        return $this.removeClass("is-modal-active");
      }, 200);
    });
  };

  Global.prototype.bindEvents = function() {
    return $("body").on("click", ".js-scroll-down", function(e) {
      var $target, position;
      e.preventDefault();
      $target = $($(this).attr("data-target"));
      position = $target.offset().top + $target.outerHeight() - 92;
      return $("html,body").animate({
        scrollTop: position
      }, config.fx.speed.mid, config.fx.easing);
    });
  };

  Global.prototype.setRoles = function() {
    var userId = $("#currentUserId").val();
    if (userId) {
     $.ajax ({
        type: "GET",
        url: "/api/user/" + userId + "/roles",
        contentType: "application/json; charset=utf-8",
        cache: false,
        async: false,
        dataType: "json",
      }).done(function(data) {
        if (data && data.roles) {
          var roles = [];
          data.roles.forEach(function(role) {
            roles.push(role.name);
          });
          localStorage.setItem("userRoles", JSON.stringify(roles));
        }
      }).fail(function(xhr) {
      });
    }
  };

  Global.prototype.getRoles = function() {
    return localStorage.getItem("userRoles") ? JSON.parse(localStorage.getItem("userRoles")) : null;
  };

  Global.prototype.checkRole = function(roleName) {
    if (roleName) {
      var roles = this.getRoles();
      if (roles) {
        return roles.indexOf(roleName) !== -1;
      } else {
        return false;
      }
    } else {
      return false;
    }
  };

  Global.prototype.reportError = function(userId, page_url, message, sync) {
    //params need to contain the following:
    //:subject_id: User on which action is being attempted
    //:message: Details of the error event
    //:page_url: The page requested resulting in the error
    var params = {};
    userId = userId || $("#currentUserId").val();
    params.subject_id = userId ? userId : 0;
    params.page_url = page_url ? page_url: window.location.href;
    //don't think we want to translate message sent back to the server here
    params.message = "Error generated in JS - " + (message ? message : "no detail available");

    $.ajax ({
        type: "GET",
        url: "/report-error",
        contentType: "application/json; charset=utf-8",
        cache: false,
        async: (sync ? false : true),
        data: params
    }).done(function(data) {
    }).fail(function(){
    });
  };

  return Global;

})();


},{"../config":1}],5:[function(require,module,exports){
var NavToggle, navExpandedClass;

navExpandedClass = "is-nav-expanded";

module.exports = NavToggle = (function() {
  function NavToggle() {
    this.build();
  }

  NavToggle.prototype.build = function() {
    $(".js-nav-menu-toggle").on("click", function(e) {
      e.preventDefault();
      return $("html").toggleClass(navExpandedClass, !$("html").hasClass(navExpandedClass));
    });
    $("figure.nav-overlay, .js-close-nav").on("click", function(e) {
      if ($("html").hasClass(navExpandedClass)) {
        return $("html").removeClass(navExpandedClass);
      }
    });
    $(".side-nav a").not("[data-toggle=modal]").on("click touchend", function(e) {
      var href;
      e.preventDefault();
      href = $(this).attr("href");
      $("html").removeClass(navExpandedClass);
      window.app.utilObj.setVis(true);
      return setTimeout(function() {
        return window.location = href;
      }, 500);
    });
    $(window).on("unload", function() {
      setTimeout(function() {
        window.app.utilObj.setVis();
      }, 500);
    });
    return $(".side-nav a[data-toggle=modal]").on("click touchend", function(e) {
      var target;
      e.preventDefault();
      target = $(this).attr("data-target");
      $("html").removeClass(navExpandedClass);
      if ($(this).attr("data-link-identifier")) {
        $("main").attr("data-link-identifier", $(this).attr("data-link-identifier"));
      }
      return setTimeout(function() {
        return $(target).modal("show");
      }, 500);
    });
  };

  return NavToggle;

})();


},{}],6:[function(require,module,exports){
var UpperBanner;

module.exports = UpperBanner = (function() {
  function UpperBanner() {
    this.build();
  }

  UpperBanner.prototype.build = function() {
    return $(".js-close-upper-banner").on("click touchstart", function(e) {
      e.preventDefault();
      return $("html").addClass("is-upper-banner-closed");
    });
  };

  UpperBanner.prototype.handleAccess = function() {
    if (typeof sessionStorage !== "undefined") {
      var data = sessionStorage.getItem('bannerAccessed');
      if (String(data) === "yes") {
        $(".js-close-upper-banner").trigger("click");
      }

      $("a.js-close-upper-banner").on("click", function() {
          sessionStorage.setItem("bannerAccessed", "yes");
      });

    }
  };

  UpperBanner.prototype.handleWatermark = function() {
    var __env = $("#env").val();
    if ((__env !== "" && __env.toLowerCase() !== "production") && ($(".watermark").length === 0)) {
      $("<div class='watermark'>TRUE<sup>NTH</sup> - " + __env + " version - Not for study or clinical use</div>").appendTo("body");
    }
  };

  return UpperBanner;

})();

},{}],7:[function(require,module,exports){
var Video, navExpandedClass;

navExpandedClass = "is-nav-expanded";

module.exports = Video = (function() {
  function Video() {
    this.build();
  }

  Video.prototype.build = function() {
    $("body").on("click", ".js-video-toggle a", function(e) {
      return e.preventDefault();
    });
    return $("body").on("click",".js-video-toggle", function(e) {
      var $div, src;
      e.preventDefault();
      $("html").addClass("is-video-active");
      $div = $(this);
      src = $div.data("iframe-src");
      return $div.append("<iframe src='" + src + "' allowfullscreen frameborder='0' />").addClass("is-js-video-active");
    });
  };

  return Video;

})();


},{}],8:[function(require,module,exports){
var Resize;

module.exports = Resize = (function() {
  function Resize() {
    var $intro;
    $intro = $(".intro");
    if (!$intro.length) {
      return;
    }
    $intro.imagesLoaded(function() {
      return $(window).on("resize.setElements", _.debounce(function(e) {
        var imgHeight;
        if ($(window).width() <= 767) {
          imgHeight = $intro.find("img.intro__img--mobile").height();
        } else {
          imgHeight = $intro.find("img.intro__img--desktop").height();
        }
        return $intro.css("height", imgHeight);
      }, 50)).trigger("resize.setElements");
    });
  }
  return Resize;

})();


},{}],9:[function(require,module,exports){
var WindowScroll;

module.exports = WindowScroll = (function() {
  function WindowScroll() {
    this.bindScroll();
  }

  WindowScroll.prototype.bindScroll = function() {
    var checkScroll;
    checkScroll = _.debounce(function() {
      var offset;
      if ($(".upper-banner").outerHeight() > 0) {
        offset = $(".upper-banner").outerHeight();
      } else {
        offset = 0;
      }
      if ($(window).scrollTop() <= offset) {
        return $("html").removeClass("is-scrolled");
      } else {
        return $("html").addClass("is-scrolled");
      }
    }, 0);
    return $(window).on("scroll.checkScroll", checkScroll).trigger("scroll.checkScroll");
  };

  return WindowScroll;

})();
},{}],
10:[function(require,module,exports){
var VisObj;

module.exports = VisObj = (function() {
  return function() {
    this.HAS_REDIRECT = false;
    this.hideMain = function () {
      $("#mainHolder").hide();
      $("#mainHolder").css({
                  "visibility" : "hidden",
                  "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=0)",
                  "filter": "alpha(opacity=0)",
                  "-moz-opacity": 0,
                  "-khtml-opacity": 0,
                  "opacity": 0
                });
    };
    this.showMain = function() {
      if (!this.HAS_REDIRECT) {
        if ($(".watermark:visible").length > 0) {
          $("header.no-banner ").css("padding-top", "35px");
        }
        $("#mainHolder").css({
                  "visibility" : "visible",
                  "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
                  "filter": "alpha(opacity=100)",
                  "-moz-opacity": 1,
                  "-khtml-opacity": 1,
                  "opacity": 1
                });
        this.hideLoader();
      };
    };
    this.showLoader = function() {
      if (!($("#loadingIndicator").is(":visible"))) {
        $("#loadingIndicator").show();
      }
    };
    this.hideLoader = function() {
      $("#loadingIndicator").hide();
    };
    this.setRedirect = function() {
      this.HAS_REDIRECT = true;
      this.showLoader();
      this.hideMain();

    };
  };
})();

},{}],
11:[function(require,module,exports){
var InterventionSessionObj;

module.exports = InterventionSessionObj = (function() {
  return function () {
    this.setInterventionSession = function(dataLinkIdentifier) {
        if (dataLinkIdentifier) {
          sessionStorage.setItem(dataLinkIdentifier+"InSession", "true");
          return;
        }
        var dataSectionId = $("main").attr("data-link-identifier");
        if (dataSectionId) {
          if (typeof sessionStorage !== "undefined") {
            sessionStorage.setItem(dataSectionId+"InSession", "true");
          }
        }
    };
    this.getSession = function(id) {
      if (!id) {
        return false;
      } else {
        return (typeof sessionStorage !== "undefined" && sessionStorage.getItem(id+"InSession"));
      }
    };
    this.clearSession = function(id) {
      if (this.getSession(id)) {
        sessionStorage.removeItem(id+"InSession");
      }
    };
  };

})();

},{}],
12:[function(require,module,exports){
var OrgTool;

module.exports = OrgTool = (function() {
  return function () {

    var OrgObj = function(orgId, orgName, parentOrg) {
      this.id = orgId;
      this.name = orgName;
      this.children = [];
      this.parentOrgId = parentOrg;
      this.isTopLevel = false;
    };

    var CONSENT_ENUM = {
        "consented": {
            "staff_editable": true,
            "include_in_reports": true,
            "send_reminders": true
        },
         "suspended": {
            "staff_editable": true,
            "include_in_reports": true,
            "send_reminders": false
        },
        "purged": {
            "staff_editable": false,
            "include_in_reports": false,
            "send_reminders": false
        }
    };

    var TOP_LEVEL_ORGS = [];
    var orgsList = {};

    this.inArray = function (val, array) {
      if (val && array) {
          for (var i = 0; i < array.length; i++) {
              if (array[i] === val) {
                return true;
              }
          };
      };
      return false;
    };

    this.getTopLevelOrgs = function() {
        return TOP_LEVEL_ORGS;
    };

    this.getOrgsList = function() {
        return orgsList;
    };
    this.setDefaultConsent =  function(userId, orgId) {
        if (!userId && !orgId) {
          return false;
        }
        var stockConsentUrl = $("#stock_consent_url").val();
        var agreementUrl = "";
        if (stockConsentUrl) {
            agreementUrl = stockConsentUrl.replace("placeholder", $("#" + orgId + "_org").attr("data-parent-name"));
        };
        if (agreementUrl) {
            var params = CONSENT_ENUM["consented"];
            params.org = orgId;
            params.agreementUrl = encodeURIComponent(agreementUrl);
            this.setConsent(userId, params, "default", true);
        };
    };
    this.setConsent = function(userId, params, status, sync) {
        var hasValue = window.app.utilObj.hasValue;
        if (userId && params) {
            var consented = this.hasConsent(userId, params["org"], status);
            if (!consented) {
                $.ajax ({
                    type: "POST",
                    url: "/api/user/" + userId + "/consent",
                    contentType: "application/json; charset=utf-8",
                    cache: false,
                    dataType: "json",
                    async: (sync? false: true),
                    data: JSON.stringify({"user_id": userId, "organization_id": params["org"], "agreement_url": params["agreementUrl"], "staff_editable": (hasValue(params["staff_editable"])? params["staff_editable"] : false), "include_in_reports": (hasValue(params["include_in_reports"]) ? params["include_in_reports"] : false), "send_reminders": (hasValue(params["send_reminders"]) ? params["send_reminders"] : false) })
                }).done(function(data) {
                }).fail(function(xhr) {
                    window.app.global.reportError(userId, "/api/user/" + userId + "/consent", xhr.responseText);
                });
            };
        };
    };
    /****** NOTE - this will return the latest updated consent entry *******/
    this.hasConsent = function(userId, orgId, filterStatus) {
        if (!userId) {
          return false;
        }
        if (!orgId) {
          return false;
        }

        var consentedOrgIds = [], expired = 0, found = false, suspended = false;
        var self = this;

        $.ajax ({
            type: "GET",
            url: "/api/user/"+userId+"/consent",
            async: false,
            cache: false
        }).done(function(data) {
            if (data.consent_agreements) {
              var d = data["consent_agreements"];
              if (d.length > 0) {
                  d = d.sort(function(a,b){
                      return new Date(b.signed) - new Date(a.signed); //latest comes first
                  });
                  var item = d[0];
                  expired = self.getDateDiff(item.expires);
                  if (item.deleted) {
                    found = true;
                  }
                  if (expired > 0) {
                    found = true;
                  }
                  if (item.staff_editable && item.include_in_reports && !item.send_reminders) {
                    suspended = true;
                  }
                  if (!found) {
                    if (String(orgId) === String(item.organization_id)) {
                      switch(filterStatus) {
                        case "suspended":
                          if (suspended) {
                            found = true;
                          }
                          break;
                        case "purged":
                          found = true;
                          break;
                        case "consented":
                          if (!suspended) {
                              if (item.staff_editable && item.send_reminders && item.include_in_reports) {
                                found = true;
                              }
                          };
                          break;
                        default:
                          found = true; //default is to return both suspended and consented entries
                      };
                      if (found) {
                        consentedOrgIds.push(orgId);
                      }

                    }
                  }
              }
            }

        }).fail(function() {
          return false;
        });
        return consentedOrgIds.length > 0 ? consentedOrgIds : null;
    };

    this.getDateDiff = function(startDate,dateToCalc) {
        var a = startDate.split(/[^0-9]/);
        var dateTime = new Date(a[0], a[1]-1, a[2]).getTime();
        var d;
        if (dateToCalc) {
            var c = dateToCalc.split(/[^0-9]/);
            d = new Date(c[0], c[1]-1, c[2]).getTime();
        } else {
            // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime();
        }
        // Round down to floor so we don't add an extra day if session is 12+ hours into the day
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24));
    };

    this.validateIdentifier = function(sync, callback) {
      if (this.identifiers) {
        return this.identifiers;
      }
      var self = this;
      $.ajax ({
        type: "GET",
        url: "/gil-shortcut-alias-validation/" + ($("#shortcut_alias").val()).toLowerCase(),
        async: sync? false : true
      }).done(function(data) {
        if (callback) {
          callback(data);
        }
      }).fail(function() {
        if (callback) {
          callback({error: "failed request"});
        }
      });

    };
    this.getOrgs = function(userId, sync, callback) {
        var self = this;
        callback = callback || function() {};
        //use common ajax function, which will retry and report error with detail
        tnthAjax.getOrgs(userId, {sync: sync}, function(data) {
          $("#fillOrgs").attr("userId", userId);
          (self.populateOrgsList).apply(self, [data.entry]);
          self.populateUI();
          $("#modal-org").on("hide.bs.modal", function(e) {
            if (typeof sessionStorage !== "undefined") {
              sessionStorage.setItem("noOrgModalViewed", "true");
            } else {
              alert(i18next.t("Unable to set session variable for organization modal viewed."));
            }
            setTimeout(function() { location.reload(); }, 0);
          });

          $("#submit-orgs").on("click", function() {
            var os = $("#userOrgs input[name='organization']:checked");
            if (os.length > 0) {
              os.each(function() {
                  if ($(this).attr("id") !== "noOrgs") {
                    var parentOrg = $(this).attr("data-parent-id");
                    if (!parentOrg) {
                      parentOrg = $(this).closest(".org-container[data-parent-id]").attr("data-parent-id");
                    };
                    var agreementUrl = $("#" + parentOrg + "_agreement_url").val();
                    if (agreementUrl && String(agreementUrl) !== "") {
                      var params = CONSENT_ENUM["consented"];
                      params.org = parentOrg;
                      params.agreementUrl = agreementUrl;
                      setTimeout(function() {
                        self.setConsent($("#currentUserId").val(), params, "all", true);
                        }, 0);
                    } else {
                      self.setDefaultConsent($("#currentUserId").val(), parentOrg);
                    };
                  };
              });
              self.updateOrg($("#currentUserId").val(), self.updateOrgCallback);
            };
          });

          $("#userOrgs input[name='organization']").each(function() {
              $(this).on("click", function() {

                  var userId = $("#fillOrgs").attr("userId");
                  var parentOrg = $(this).attr("data-parent-id");

                  if ($(this).prop("checked")){
                      if ($(this).attr("id") !== "noOrgs") {
                          $("#noOrgs").prop("checked",false);

                      } else {
                          $("#userOrgs input[name='organization']").each(function() {
                             if ($(this).attr("id") !== "noOrgs") {
                                  $(this).prop("checked",false);
                              };
                          });

                      };
                  };
              });
          });
          callback(data);
        });
    },
    this.updateOrg = function(userId, callback) {

        var demoArray = {}, errorMessage = "", hasValue = window.app.utilObj.hasValue;

        $.ajax ({
            type: "GET",
            url: "/api/demographics/"+userId,
            async: false
        }).done(function(data) {
            demoArray = data;
        }).fail(function() {
            errorMessage = i18next.t("Error retrieving demographics information for user.");
        });

        var orgIDs = $("#userOrgs input[name='organization']:checked").map(function(){
            return { reference: "api/organization/"+$(this).val() };
        }).get();

        if (!hasValue(errorMessage)) {
          if (typeof orgIDs === "undefined"){
              orgIDs = [0];  // special value for `none of the above`
          }
          demoArray["careProvider"] = orgIDs;

          $.ajax ({
              type: "PUT",
              url: "/api/demographics/"+userId,
              contentType: "application/json; charset=utf-8",
              dataType: "json",
              async: true,
              data: JSON.stringify(demoArray)
          }).done(function(data) {
              if (callback) {
                callback(errorMessage);
              }
          }).fail(function() {
              errorMessage += (hasValue(errorMessage) ? "<br/>":"") + i18next.t("Error occurred updating user organization.");
              if (callback) {
                callback(errorMessage);
              }
          });
        } else {
          if(typeof callback !== "undefined") {
            callback(errorMessage);
          }
        };

    },

    this.filterOrgs = function(leafOrgs) {
        if (!leafOrgs) {
          return false;
        }

        var self = this;

        $("input[name='organization']:checkbox").each(function() {
            if (! self.inArray($(this).val(), leafOrgs)) {
                $(this).hide();
                if (orgsList[$(this).val()] && orgsList[$(this).val()].children.length === 0) {
                  $(this).closest("label").hide();
                }
            };
        });

        var topList = self.getTopLevelOrgs();

        topList.forEach(function(orgId) {
            var allChildrenHidden = true;
            $(".org-container[data-parent-id='" + orgId + "']").each(function() {
                var subOrgs = $(this).find(".org-container");
                if (subOrgs.length > 0) {
                    var allSubOrgsHidden = true;
                    subOrgs.each(function() {
                         var isVisible = false;
                         $(this).find("input[name='organization']").each(function() {
                             if ($(this).is(":visible")) {
                                isVisible = true;
                                allChildrenHidden = false;
                             }
                         });
                        if (!isVisible) {
                            $(this).hide();
                        } else {
                          allSubOrgsHidden = false;
                        }

                    });

                    if (allSubOrgsHidden) {
                      $(this).children("label").hide();
                    }

                } else {
                    var ip = $(this).find("input[name='organization']");
                    if (ip.length > 0) {
                      ip.each(function() {
                        if ($(this).is(":visible")) {
                          allChildrenHidden = false;
                        }
                      });
                    }
                }
            });
            if (allChildrenHidden) {
                $("#fillOrgs").find("legend[orgid='" + orgId + "']").hide();
            }

        });
    };

    this.findOrg = function(entry, orgId) {
        var org;
        if (entry && orgId) {
            entry.forEach(function(item) {
              if (!org) {
                if (String(item.id) === String(orgId)) {
                  org = item;
                }
              }
            });
        }
        return org;
    };
    this.getTopLevelOrgs = function() {
        if (TOP_LEVEL_ORGS.length === 0) {
            var topOrgs = $("#fillOrgs").find('input[name="organization"][parent_org="true"]');
            if (topOrgs.length > 0) {
                topOrgs.each(function() {
                    TOP_LEVEL_ORGS.push[$(this).val()];
                });
            }
        };
        return TOP_LEVEL_ORGS;
    };

    this.populateOrgsList = function(items) {
        if (!items) {
          return false;
        }
        var entry = items, self = this, parentId;
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (!orgsList[parentId]) {
                    var o = self.findOrg(entry, parentId);
                    orgsList[parentId] = new OrgObj(o.id, o.name);
                };
                orgsList[parentId].children.push(new OrgObj(item.id, item.name, parentId));
                if (orgsList[item.id]) {
                  orgsList[item.id].parentOrgId = parentId;
                }
                else {
                  orgsList[item.id] = new OrgObj(item.id, item.name, parentId);
                }
            } else {
                if (!orgsList[item.id]) {
                  orgsList[item.id] = new OrgObj(item.id, item.name);
                }
                if (parseInt(item.id) !== 0) {
                  orgsList[item.id].isTopLevel = true;
                  TOP_LEVEL_ORGS.push(item.id);
                };
            };
        });
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (orgsList[item.id]) {
                  orgsList[item.id].parentOrgId = parentId;
                }
            };
        });
        return orgsList;
    };

    this.populateUI = function() {
        var parentOrgsCt = 0, topLevelOrgs = this.getTopLevelOrgs();
        for (var org in orgsList) {
            if (orgsList[org].isTopLevel) {
                if (orgsList[org].children.length > 0) {
                  $("#fillOrgs").append("<legend orgId='" + org + "'>"+i18next.t(orgsList[org].name)+"</legend><input class='tnth-hide' type='radio' name='organization' parent_org=\"true\" org_name=\"" + orgsList[org].name + "\" id='" + orgsList[org].id + "_org' value='"+orgsList[org].id+"' />");

                } else {
                  $("#fillOrgs").append('<div id="' + orgsList[org].id + '_container" data-parent-id="'+ orgsList[org].name +'"  data-parent-name="' + orgsList[org].name + '" class="org-container"><label id="org-label-' + orgsList[org].id + '" class="org-label"><input class="clinic" type="radio" name="organization" parent_org="true" id="' +  orgsList[org].id + '_org" value="'+
                        orgsList[org].id +'"  data-parent-id="'+ orgsList[org].id +'"  data-parent-name="' + orgsList[org].name + '"/><span>' + i18next.t(orgsList[org].name) + '</span></label></div>');
                }
                parentOrgsCt++;
            };
            // Fill in each child clinic
            if (orgsList[org].children.length > 0) {
                var childClinic = "";
                orgsList[org].children.forEach(function(item, index) {
                    var _parentOrgId = item.parentOrgId;
                    var _parentOrg = orgsList[_parentOrgId];
                    var _isTopLevel = _parentOrg ? _parentOrg.isTopLevel : false;
                    childClinic = '<div id="' + item.id + '_container" ' + (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") +' class="indent org-container">'

                    if (orgsList[item.id].children.length > 0) {
                        childClinic += '<label class="org-label ' + (orgsList[item.parentOrgId].isTopLevel ? "text-muted": "text-muter") + '">' +
                        '<input class="clinic" type="radio" name="organization" id="' +  item.id + '_org" value="'+
                        item.id +'"  ' +  (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") + '/><span>'+
                        i18next.t(item.name) +
                        '</span></label>';

                     } else {
                        childClinic += '<label class="org-label">' +
                        '<input class="clinic" type="radio" name="organization" id="' +  item.id + '_org" value="'+
                        item.id +'"  ' +  (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") + '/><span>'+
                        i18next.t(item.name) +
                        '</span></label>';
                    }

                    childClinic += '</div>';

                    if ($("#" + _parentOrgId + "_container").length > 0) $("#" + _parentOrgId + "_container").append(childClinic);
                    else {
                      $("#fillOrgs").append(childClinic);
                    }

                });
            };

            if (parentOrgsCt > 0 && orgsList[org].isTopLevel) {
              $("#fillOrgs").append("<span class='divider'>&nbsp;</span>");
            }
        };
    };
    this.handleNoOrgs = function (userId) {
        $(".intervention-link, a.decision-support-link").each(function() {
          var dm = /decision\s?support/gi;
          if (dm.test($(this).text()) || $(this).hasClass("decision-support-link")) {
            var hasSet = (typeof sessionStorage != "undefined") && sessionStorage.getItem("noOrgModalViewed");
            //allow modal to show once once action has been taken
            if (hasSet) {
              return false;
            }
            var self = this;
            $.ajax ({
               type: "GET",
                url: "/api/demographics/" + userId,
                async: false
            }).done(function(data) {
              if (data && data.careProvider) {
                  $.each(data.careProvider,function(i,val){
                    var orgID = val.reference.split("/").pop();
                    if (parseInt(orgID) === 0) {
                        $(self).removeAttr("href");
                        $(self).on("click", function() {
                          $("figure.js-close-nav").trigger("click");
                          setTimeout(function() {
                            $("#modal-org").modal("show");
                          }, 0);
                        });
                        window.app.interventionSessionObj.clearSession("decision-support");
                    };
                  });
                };
            }).fail(function(xhr) {
                 window.app.global.reportError(userId, "/api/demographics/" + userId, xhr.responseText);
            });
          };
       });
    };

    this.updateOrgCallback = function (errorMessage) {
      if (!errorMessage) {
          $("#modal-org a.box-modal__close").trigger("click");
          window.app.utilObj.setVis(true);
          setTimeout(function() { location.reload(); }, 1000);
          if (typeof sessionStorage !== "undefined") {
            sessionStorage.setItem("noOrgModalViewed", "true");
          }
      } else {
        $("#modal-org-error").html(i18next.t("Error updating organization"));
      }
    };
  };

})();
},{}],
13:[function(require,module,exports){
  var menuObj;
  module.exports = menuObj = (function() {
      return function () {
          this.init = function(currentUserId, callback) {
            callback = callback || function() {};
            this.setSelectedNavItem($(".side-nav-items__item--" + $("main").attr("data-section")));
            this.handleDisabledLinks();
            if ($("main").attr("data-section") === "about") {
              $("#repoVersion").show();
            }
            if (window.app.global.checkRole("patient") || window.app.global.checkRole("partner")) {
              this.filterMenu(currentUserId, callback);
            } else {
              window.app.visObj.hideLoader();
              callback();
            }
          };
          this.handleDisabledLinks = function() {
            if (window.app.utilObj.getUrlParameter("disableLinks")) {
              $("nav.side-nav li.side-nav-items__item, footer .nav-list__item").each(function() {
                if (!$(this).hasClass("side-nav-items__item--home") &&
                  !$(this).hasClass("side-nav-items__item--logout") &&
                  !$(this).hasClass("nav-list__item--home")) {
                    $(this).children("a").each(function() {
                      $(this).addClass("disabled");
                      $(this).prop("onclick",null).off("click");
                      $(this).on("click", function(e) {
                        e.preventDefault();
                        return false;
                      });
                  });
                }
              });
            }
          };
          this.setSelectedNavItem = function(obj) {
            $(obj).addClass("side-nave-items__item--selected");
            $("li.side-nave-items__item--selected").find("a").attr("href", "#");
            $(obj).on("click", function(event) {
              event.preventDefault();
              window.app.utilObj.setVis(false);
              $(".side-nav__close").trigger("click");
              return;
            });
          };
          this.disableInterventionLink = function(itemName) {
            $("." + itemName + "-link").each(function() {
              $(this).removeAttr("href");
              $(this).addClass("icon-box__button--disabled");
            });
            $(".icon-box-" + itemName).addClass("icon-box--theme-inactive");
            window.app.interventionSessionObj.clearSession(itemName);
            return false;
          },
          this.handleItemRedirect = function(userId, itemName) {
            var visObj = window.app.visObj;
            window.app.orgTool.handleNoOrgs(userId);
            if (!window.app.interventionSessionObj.getSession(itemName)) {
              return false;
            }
            var l =  $("#intervention_item_" + itemName + " a");
            var la = l.attr("href");
            if (l.length > 0 && window.app.utilObj.validateUrl(la)) {
              window.app.interventionSessionObj.clearSession(itemName);
              visObj.setRedirect();
              setTimeout(function() {
                location.replace(l.attr("href"));
              }, 0);
              return true;
            }
            return false;
          };
          this.resetLinkElement = function(linkElement) {
            if (!linkElement) {
              return false;
            }
            linkElement.removeAttr("data-toggle");
            linkElement.removeAttr("data-target");
            linkElement.unbind("click");
          },
          this.setItemVis = function(item, itemLink, vis) {
            if (item) {
              this.resetLinkElement(item);
              switch(vis) {
                case "disabled":
                  item.removeAttr("href");
                  item.addClass("icon-box__button--disabled");
                  break;
                default:
                  item.attr("href", itemLink);
                  item.removeClass("icon-box__button--disabled");
              }
            }
          };
          this.setDashboardMenuItem = function(domain) {
            domain = domain || "";
            var db = $(".side-nav-items__item--dashboard");
            if (! (db.length === 0)) {
              return;
            }
            $(".side-nav-items").prepend('<li class="side-nav-items__item side-nav-items__item--dashboard"><a href="' + domain + '/home">' + i18next.t("My Dashboard") + '</a></li>');
            if ($("#portalMain").length) { //currently at the patient portal page
              this.setSelectedNavItem($(".side-nav-items__item--dashboard"));
              $(".side-nav-items__item--home").hide(); 
            }
          };
          this.handleInterventionItemLinks = function(interventionItem, customName){
            var self = this;
            if (interventionItem) {
              var link = interventionItem.link_url;
              var disabled = (String(link) === "disabled");
              var itemName = customName||interventionItem.name;
              var linkItems = $("." + itemName + "-link");
              var menuItem = $("#intervention_item_" + itemName);
              if (!disabled && menuItem.length === 0) { //only draw this when there isn't already one
                $(".side-nav-items__item--dashboard").after('<li id="intervention_item_' + itemName + '" class="side-nav-items__item side-nav-items__item--has-icon side-nav-items__item--accentuated"><a href="' + link + '" class="capitalize intervention-link">' + interventionItem.description + '</a></li>');
              }
              if (linkItems.length > 0) {
                if (!disabled) {
                  linkItems.each(function() {
                    self.setItemVis($(this), link);
                  });
                  $(".icon-box-" + itemName).removeClass("icon-box--theme-inactive");
                } else {
                  linkItems.each(function() {
                    self.setItemVis($(this), link, "disabled");
                  });
                  $(".icon-box-" + itemName).addClass("icon-box--theme-inactive");
                  this.disableInterventionLink(itemName);
                }
              }
            }
          };
          this.filterMenu = function (userId, callback) {
            callback = callback || function() {};
            if (!userId) {
              callback({error: true});
              return false;
            }
            var self = this;
            var __PORTAL = $("#portalURI").val();
            $.ajax({
              url: __PORTAL + "/gil-interventions-items/" + userId,
              context: document.body,
              async: false,
              cache: false
            }).done(function(data) {
              var found_decision_support = false, found_symptom_tracker = false;
              if (!data.interventions || !(data.interventions.length)) {
                callback({error: true});
                return false;
              }
              //add patient dashboard home link if not already present
              self.setDashboardMenuItem(__PORTAL);
              const DECISION_SUPPORT_ID = "decision-support";
              const SYMPTOM_TRACKER_ID = "symptom-tracker";
              (data.interventions).forEach(function(item) {
                var itemDescription = item.description;
                var itemName = item.name.replace(/\_/g, " ");
                var disabled = item.link_url == "disabled";
                var dm = /decision\s?support/gi;
                var sm = /symptom\s?tracker/gi;
                var sm2 = /self[_\s]?management/gi;
                if (dm.test(itemDescription) || dm.test(itemName)) {
                  found_decision_support = !disabled;
                  self.handleInterventionItemLinks(item, DECISION_SUPPORT_ID);
                } else if (sm.test(itemDescription) || sm2.test(itemName)) {
                  found_symptom_tracker = !disabled;
                  self.handleInterventionItemLinks(item, SYMPTOM_TRACKER_ID);
                } else if ($.trim(itemDescription) !== "") {
                  self.handleInterventionItemLinks(item);
                };
            });
            if (self.handleItemRedirect(userId, DECISION_SUPPORT_ID, found_decision_support) ||
                self.handleItemRedirect(userId, SYMPTOM_TRACKER_ID, found_symptom_tracker)
            ) {
              return true;
            }
            callback();
            window.app.utilObj.setVis(false);
          }).fail(function() {
            callback({error: true});
            window.app.utilObj.setVis(false);
          });
        };
      };
  })();
},{}],
14:[function(require,module,exports){
var accessCodeObj;

module.exports = accessCodeObj = (function() {
  return function() {
    this.handleAccessCode = function() {
      if ($("#shortcut_alias").val() !== "" && $("#access_code_error").text() === "") {
        $("#access_code_info").show();
        $("#accessCodeLink").addClass("icon-box__button--disabled");
        $("#btnCreateAccount").removeAttr("href").addClass("icon-box__button--disabled");
        $("#shortcut_alias").attr("disabled", true);
        window.app.interventionSessionObj.setInterventionSession();
        setTimeout(function() { location.replace("/go/" + ($("#shortcut_alias").val()).toLowerCase());}, 4000);
      } else {
        if ($("#access_code_error").text() !== "") {
          $("#access_code_error").show();
        }
      }
    };
    this.handleEvents = function() {
        var self = this;
        $("#shortcut_alias").on("keyup paste", function(e) {
          if ($(this).val() !== "") {
            window.app.orgTool.validateIdentifier(false,
              function(data) {
                if (data) {
                  if (data.name) {
                    $("#access_code_info").html(i18next.t("Thank you, your access code {shortcut_alias} indicates you are located at the {org_name}. Proceeding to registration ...").replace("{shortcut_alias}", "<b>"+$("#shortcut_alias").val()+"</b>").replace("{org_name}", "<b>"+data.name+"</b>"));
                      $("#access_code_error").text("");

                    } else {
                      if (data.error) {
                        $("#access_code_info").text("");
                        $("#access_code_error").text(i18next.t("You have entered an invalid access code.  Please try again"));
                      }
                  }
                } else {
                    if ($("#shortcut_alias").val() !== "") {
                      $("#access_code_info").text("");
                      $("#access_code_error").text(i18next.t("System was unable to process your request."));
                    }
                }

              });
          } else {
            $("#access_code_info").text("");
          }
        }).on("keydown", function(e) {
          if (e.keyCode === RETURN_KEY_CODE) {
            e.preventDefault();
            self.handleAccessCode();
          }
        });

        $("#accessCodeLink").on("click", function() {
          self.handleAccessCode();
        });
    };

  }

})();
},{}],
15:[function(require,module,exports){
var utilObj;
module.exports = utilObj = (function() {
  return function() {
    /*********
     *
     * general global utilities function
     *
     *********/
    this.handlePostLogout = function() {
      if ($("main[data-section='home']").length) {
        Utility.handlePostLogout(); /*global Utility handlePostLogout */
      }
    };

    this.setSVGSupportAttr = function() {
      if (Utility.supportSVG()) {
        $("body").addClass("allow-svg");
      }
    };

    this.setVis = function(show) {
      if (show) {
        window.app.visObj.showLoader();
      } else {
        window.app.visObj.showMain();
      }
    };

    this.LRKeyEvent = function() {
      if ($(".button--LR").length > 0) {
        $("html").on("keydown", function(e) {
          var LR_INVOKE_KEYCODE = 187; // "=" sign
          if (e.keyCode === LR_INVOKE_KEYCODE) {
            $(".button--LR").toggleClass("show");
          }
        });
      }
    };

    this.appendLREditContainer = function(target, url, show) {
      if (!url) {
        return false;
      }
      if (!target) {
        target = $(document);
      }
      target.append("<div>" +
                  '<a href="' + url + '" target="_blank" class="menu button button--small button--teal button--LR">' + i18next.t("Edit in Liferay") + '</a>' +
                  "</div>"
                  );
      if (show) {
        $(".button--LR").addClass("show");
      }
    };
    this.hasValue = function(val) {
      return val != null && val != "" && val != "undefined";
    };
  
    this.validateUrl = function(val) {
      if (!val) {
        return false;
      }  
      //this test for full URL - "https://stg-sm.us.truenth.org" etc.
      if (val.indexOf('http') !== -1 || val.indexOf('https') !== -1) {
        return  $.trim(val) !== "#" && /^(https?|ftp)?(:)?(\/\/)?([a-zA-Z0-9.-]+(:[a-zA-Z0-9.&%$-]+)*@)*((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}|([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(:[0-9]+)*(\/($|[a-zA-Z0-9.,?'\\+&%$#=~_-]+))*$/.test(val);
      }
      return $.trim(val) !== "#"; 
    };

    this.getUrlParameter = function (name) {
      name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
      var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
      var results = regex.exec(location.search);
      return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    };
    this.initSessionMonitor = function() {
      /*
       * get portal wrapper nav content
       * this contains session monitor & piwik setups
       */
      $.ajax({
          url: $("#portalURI").val() + "/api/portal-wrapper-html/",
          type: "GET",
          contentType:"text/plain"
      }, "html")
      .done(function(data) {
          $("#portalWrapperNav")
          // Embed data returned by AJAX call into container element
          .html(data);
      })
      .fail(function(xhr) {
          /*
           * report error
           */
          var params = {};
          params.subject_id = $("#currentUserId").val() ? $("#currentUserId").val() : 0;
          params.page_url = window.location.href;
          //don't think we want to translate message sent back to the server here
          params.message = "In GIL, error loading nav elements from portal - " + ("status code: "+ xhr.status) + "\nresponse: " + (xhr.responseText?xhr.responseText:"empty");

          $.ajax ({
              type: "GET",
              url: "/report-error",
              contentType: "application/json; charset=utf-8",
              cache: false,
              async: true,
              data: params
          }).done(function(data) {
          });
      });
    };

    this.setFooter = function(currentUserId) {
      tnthAjax.getPortalFooter("", false,  false, function(data) {
        $("footer").html(data);
        window.app.menuObj.filterMenu(currentUserId);
      });
    };

    this.handleLoginAsUser = function() {
      var __LOGIN_AS_PATIENT = (typeof sessionStorage !== "undefined") ? sessionStorage.getItem("loginAsPatient") : null;
      if (__LOGIN_AS_PATIENT) {
        if (typeof history !== "undefined" && history.pushState) {
          history.pushState(null, null, location.href);
        }
        window.addEventListener("popstate", function(event) {
          if (typeof history !== "undefined" && history.pushState) {
            history.pushState(null, null, location.href);
            setTimeout(function() { location.reload(); } , 0);
          } else {
            window.history.forward(1);
            setTimeout(function() { location.reload();}, 0);
          }
        });
      }
    };
  };
})();
},{}]
},{},[2]);

$(document).ready(function(){
  //note: display system outage message only after i18next has been instantiated - allowing message to be translated
  Utility.displaySystemOutageMessage(); /* global Utility displaySystemOutageMessage */
  var currentUserId = $("#currentUserId").val();
  // Configure and start the session timeout monitor
  if (currentUserId !== "") {
    window.app.utilObj.handleLoginAsUser();
    window.app.orgTool.getOrgs(currentUserId);
  } else {
    window.app.utilObj.handlePostLogout();
  }
  window.app.utilObj.setFooter(currentUserId); 
  window.app.utilObj.initSessionMonitor();

  $(".button--login--register").on("click", function () {
    $("#modal-login-register").modal("hide");
    setTimeout(function() { $("#modal-login").modal("show"); }, 400);
  });

  $("#modal-login").on("show.bs.modal", function(e) {
    window.app.utilObj.setVis(false);
  });

  $("#btnCreateAccount").on("click", function() {
    window.app.interventionSessionObj.setInterventionSession();
  });

  $("a.icon-box__button--disabled, .side-nave-items__item--selected a").on("click", function(e) {
    e.preventDefault();
    window.app.utilObj.setVis(false);
    return false;
  });

  $("#password").on("keyup", function() {
    if (e.keyCode === RETURN_KEY_CODE) {
      e.preventDefault();
      if ($("input[name='email']").val() !== "") {
        $("#btnLogin").trigger("click");
      }
    }
  });

  $("input[type='text']").on("blur paste", function() {
    $(this).val($.trim($(this).val()));
  });

  if ($("#sessionTimedOut").val() === "true") {
    $("#timeout-modal").modal("show");
  }

  if ($("main").attr("data-theme") === "white") {
    $("body").addClass("theme--intro-light");
  }

  if (String($("#showFlashMessageModal").val()).toLowerCase() === "true") {
    $("#alertModal").modal("show");
  }
  window.app.upperBanner.handleAccess();
  window.app.upperBanner.handleWatermark();
  window.app.accessCodeObj.handleEvents();
  window.app.utilObj.appendLREditContainer($("main .LR-content-container"), $("#LREditorURL").val(), window.app.global.checkRole("content_manager"));
  window.app.menuObj.init(currentUserId, function() { //enable/disabled menu items depending on user roles
    window.app.utilObj.setSVGSupportAttr();
    window.app.utilObj.setVis(false);
  });
});

