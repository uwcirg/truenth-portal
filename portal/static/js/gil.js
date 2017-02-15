(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);throw new Error("Cannot find module '"+o+"'")}var f=n[o]={exports:{}};t[o][0].call(f.exports,function(e){var n=t[o][1][e];return s(n?n:e)},f,f.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
module.exports = {
  fx: {
    easing: 'easeOutExpo',
    speed: {
      slow: 1500,
      mid: 1000,
      fast: 1000
    }
  }
};


},{}],2:[function(require,module,exports){
var admin, global, navToggle, upperBanner, video, windowResize, windowScroll;

upperBanner = require('./modules/upper-banner');

windowScroll = require('./modules/window-scroll');

windowResize = require('./modules/window-resize');

navToggle = require('./modules/nav-toggle');

global = require('./modules/global');

admin = require('./modules/admin');

video = require('./modules/video');

$(function() {
  if (window.app == null) {
    window.app = {};
  }
  window.app.global = new global();
  window.app.upperBanner = new upperBanner();
  window.app.windowScroll = new windowScroll();
  window.app.windowResize = new windowResize();
  window.app.navToggle = new navToggle();
  window.app.admin = new admin();
  return window.app.video = new video();
});


},{"./modules/admin":3,"./modules/global":4,"./modules/nav-toggle":5,"./modules/upper-banner":6,"./modules/video":7,"./modules/window-resize":8,"./modules/window-scroll":9}],3:[function(require,module,exports){
var Admin, loggedInAdminClass, loggedInClass, upperBannerClosedClass;

loggedInAdminClass = 'is-showing-logged-in';

loggedInClass = 'is-logged-in';

upperBannerClosedClass = 'is-upper-banner-closed';

module.exports = Admin = (function() {
  function Admin() {
    this.build();
  }

  Admin.prototype.build = function() {
    return $('.js-mock-submit').on('submit', function(e) {
      e.preventDefault();
      return $(this).addClass('is-submitted');
    });
  };

  return Admin;

})();


},{}],4:[function(require,module,exports){
var Global, config;

config = require('../config');

module.exports = Global = (function() {
  function Global() {
    this.addFX();
    this.addPlugins();
    this.bindEvents();
  }

  Global.prototype.addFX = function() {
    return $.extend($.easing, window.easing);
  };

  Global.prototype.addPlugins = function() {
    $('.modal').on('show.bs.modal', function(e) {
      return $(this).addClass('is-modal-active');
    });
    return $('.modal').on('hide.bs.modal', function(e) {
      var $this;
      $this = $(this);
      return setTimeout(function() {
        return $this.removeClass('is-modal-active');
      }, 200);
    });
  };

  Global.prototype.bindEvents = function() {
    return $('.js-scroll-down').on('click', function(e) {
      var $target, position;
      e.preventDefault();
      $target = $($(this).attr('data-target'));
      position = $target.offset().top + $target.outerHeight() - 92;
      return $('html,body').animate({
        scrollTop: position
      }, config.fx.speed.mid, config.fx.easing);
    });
  };

  return Global;

})();


},{"../config":1}],5:[function(require,module,exports){
var NavToggle, navExpandedClass;

navExpandedClass = 'is-nav-expanded';

module.exports = NavToggle = (function() {
  function NavToggle() {
    this.build();
  }

  NavToggle.prototype.build = function() {
    $('.js-nav-menu-toggle').on('click', function(e) {
      e.preventDefault();
      return $('html').toggleClass(navExpandedClass, !$('html').hasClass(navExpandedClass));
    });
    $("figure.nav-overlay, .js-close-nav").on('click', function(e) {
      if ($('html').hasClass(navExpandedClass)) {
        return $('html').removeClass(navExpandedClass);
      }
    });
    $('.side-nav a').not('[data-toggle=modal]').on('click touchend', function(e) {
      var href;
      e.preventDefault();
      href = $(this).attr('href');
      $('html').removeClass(navExpandedClass);
      loader(true);
      return setTimeout(function() {
        return window.location = href;
      }, 500);
    });
    return $('.side-nav a[data-toggle=modal]').on('click touchend', function(e) {
      var target;
      e.preventDefault();
      target = $(this).attr('data-target');
      $('html').removeClass(navExpandedClass);
      return setTimeout(function() {
        return $(target).modal('show');
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
    return $('.js-close-upper-banner').on('click touchstart', function(e) {
      e.preventDefault();
      return $('html').addClass('is-upper-banner-closed');
    });
  };

  return UpperBanner;

})();


},{}],7:[function(require,module,exports){
var Video, navExpandedClass;

navExpandedClass = 'is-nav-expanded';

module.exports = Video = (function() {
  function Video() {
    this.build();
  }

  Video.prototype.build = function() {
    $('.js-video-toggle a').on('click', function(e) {
      return e.preventDefault();
    });
    return $('.js-video-toggle').on('click', function(e) {
      var $div, src;
      e.preventDefault();
      $('html').addClass('is-video-active');
      $div = $(this);
      src = $div.data('iframe-src');
      return $div.append("<iframe src='" + src + "' allowfullscreen frameborder='0' />").addClass('is-js-video-active');
    });
  };

  return Video;

})();


},{}],8:[function(require,module,exports){
var Resize;

module.exports = Resize = (function() {
  function Resize() {
    var $intro;
    $intro = $('.intro');
    $intro.imagesLoaded(function() {
      return $(window).on('resize.setElements', _.debounce(function(e) {
        var imgHeight;
        if ($(window).width() <= 767) {
          imgHeight = $intro.find('img.intro__img--mobile').height();
        } else {
          imgHeight = $intro.find('img.intro__img--desktop').height();
        }
        return $intro.css('height', imgHeight);
      }, 50)).trigger('resize.setElements');
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
      if ($('.upper-banner').outerHeight() > 0) {
        offset = $('.upper-banner').outerHeight();
      } else {
        offset = 0;
      }
      if ($(window).scrollTop() <= offset) {
        return $('html').removeClass('is-scrolled');
      } else {
        return $('html').addClass('is-scrolled');
      }
    }, 0);
    return $(window).on('scroll.checkScroll', checkScroll).trigger('scroll.checkScroll');
  };

  return WindowScroll;

})();


},{}]},{},[2])

$("input[type='text']").on("blur paste", function() {
      $(this).val($.trim($(this).val()));
});
var LOGIN_AS_PATIENT = (typeof sessionStorage != "undefined") ? sessionStorage.getItem("loginAsPatient") : null;
if (LOGIN_AS_PATIENT) {
    if (typeof history != 'undefined' && history.pushState) history.pushState(null, null, location.href);
    window.addEventListener('popstate', function(event) {
      if (typeof history != 'undefined' && history.pushState) {
        history.pushState(null, null, location.href);
        setTimeout('location.reload();', 0);
      } else {
        window.history.forward(1);
        setTimeout('location.reload();', 0);
      };
    });
};

function setNoBanner() {
    if (typeof sessionStorage != "undefined") {
      sessionStorage.setItem('bannerAccessed', 'yes');
    };
};

function checkBannerStatus() {
  if (typeof sessionStorage != "undefined") {
    var data = sessionStorage.getItem('bannerAccessed');
    if (data == "yes") {
      $('.js-close-upper-banner').trigger("click");
    };
  }
};
function goToLogin() {
    $('#modal-login-register').modal('hide');
    setTimeout("$('#modal-login').modal('show'); ", 400);
};
function setSelectedNavItem(obj) {
    $(obj).addClass("side-nave-items__item--selected");
    $("li.side-nave-items__item--selected").find("a").attr("href", "#");

    $(obj).on("click", function(event) {
          event.preventDefault();
          $(".side-nav__close").trigger("click");
          return;
     });
};

function handleAccessCode() {
  if ($("#shortcut_alias").val() != "" && $("#access_code_error").text() == "") {
    $("#access_code_info").show();
    $(this).addClass("icon-box__button--disabled");
    IO.setInterventionSession();
    setTimeout('location.replace("/go/" + $("#shortcut_alias").val());', 1800);
  } else {
    if ($("#access_code_error").text() != "") $("#access_code_error").show();
  };
};

var InterventionSessionObj = function() {
    var SESSION_ID_ENUM = {
      "decision-support": "decisionSupportInSession",
      "symptom-tracker": "symptomTrackerInSession"
    };

    this.setInterventionSession = function() {
        var inDecisionSupport = $("main.decision-support-main").length > 0;
        var inSymptomTracker = $("main.symptom-tracker-main").length > 0;
        if (inDecisionSupport) {
            if (typeof sessionStorage != "undefined") {
               try {
                 sessionStorage.setItem(SESSION_ID_ENUM["decision-support"], "true");
               } catch(e) {

               };
            };
        };
        if (inSymptomTracker) {
            if (typeof sessionStorage != "undefined") {
               try {
                 sessionStorage.setItem(SESSION_ID_ENUM["symptom-tracker"], "true");
               } catch(e) {

               };
            };
        };
    };
    this.getSession = function(id) {
      if (!id) return false;
      else return (typeof sessionStorage != "undefined" && sessionStorage.getItem(SESSION_ID_ENUM[id]));
    };
    this.clearSession = function(type) {
        switch(type) {
          case "decision-support":
            if (this.getSession("decision-support")){
                sessionStorage.removeItem(SESSION_ID_ENUM["decision-support"])
            };
            break;
          case "symptom-tracker":
            if (this.getSession("symptom-tracker")){
                sessionStorage.removeItem(SESSION_ID_ENUM["symptom-tracker"])
            };
            break;
          default:
            //remove all
            for (var item in SESSION_ID_ENUM) {
              this.clearSession(item);
            };
            break;
        };
    };
};

var IO = new InterventionSessionObj();

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

function hasValue(val) {
    return val != null && val != "" && val != "undefined";
};
//this test for full URL - "https://stg-sm.us.truenth.org" etc.
function validateUrl(val) {
    return  hasValue(val) && $.trim(val) != "#" &&/^(https?|ftp)?(:)?(\/\/)?([a-zA-Z0-9.-]+(:[a-zA-Z0-9.&%$-]+)*@)*((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}|([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(:[0-9]+)*(\/($|[a-zA-Z0-9.,?'\\+&%$#=~_-]+))*$/.test(val);
};

var OrgTool = function() {

    var TOP_LEVEL_ORGS = [];
    var orgsList = {};

    this.inArray = function (val, array) {
        if (val && array) {
            for (var i = 0; i < array.length; i++) {
                if (array[i] == val) return true;
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
    this.setConsent = function(userId, params, status, sync) {
        if (userId && params) {
            var consented = this.hasConsent(userId, params["org"], status);
            if (!consented) {
                $.ajax ({
                    type: "POST",
                    url: '/api/user/' + userId + '/consent',
                    contentType: "application/json; charset=utf-8",
                    cache: false,
                    dataType: 'json',
                    async: (sync? false: true),
                    data: JSON.stringify({"user_id": userId, "organization_id": params["org"], "agreement_url": params["agreementUrl"], "staff_editable": (hasValue(params["staff_editable"])? params["staff_editable"] : false), "include_in_reports": (hasValue(params["include_in_reports"]) ? params["include_in_reports"] : false), "send_reminders": (hasValue(params["send_reminders"]) ? params["send_reminders"] : false) })
                }).done(function(data) {
                    //console.log("consent updated successfully.");
                }).fail(function(xhr) {
                    //console.log("request to updated consent failed.");
                    //console.log(xhr.responseText)
                });
            };
        };
    };
    /****** NOTE - this will return the latest updated consent entry *******/
    this.hasConsent = function(userId, orgId, filterStatus) {
        if (!userId) return false;
        if (!orgId) return false;

        var consentedOrgIds = [], expired = 0, found = false, suspended = false;

        $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+"/consent",
            async: false,
            cache: false
        }).done(function(data) {
            if (data.consent_agreements) {
                var d = data["consent_agreements"];
                if (d.length > 0) {
                    d = d.sort(function(a,b){
                        return new Date(b.signed) - new Date(a.signed); //latest comes first
                    });
                    item = d[0];
                    expired = OT.getDateDiff(item.expires);
                    if (item.deleted) found = true;
                    if (expired > 0) found = true;
                    if (item.staff_editable && item.include_in_reports && !item.send_reminders) suspended = true;
                    if (!found) {
                        if (orgId == item.organization_id) {
                            //console.log("consented orgid: " + orgId)
                            switch(filterStatus) {
                                case "suspended":
                                    if (suspended) found = true;
                                    break;
                                case "purged":
                                    found = true;
                                    break;
                                case "consented":
                                    if (!suspended) {
                                        if (item.staff_editable && item.send_reminders && item.include_in_reports) found = true;
                                    };
                                    break;
                                default:
                                    found = true; //default is to return both suspended and consented entries
                            };
                            if (found) consentedOrgIds.push(orgId);

                        };
                    };
                }
            };

        }).fail(function() {
            return false;
         });
        //console.log(consentedOrgIds)
        return consentedOrgIds.length > 0 ? consentedOrgIds : null;
    };

    this.getDateDiff = function(startDate,dateToCalc) {
        var a = startDate.split(/[^0-9]/);
        var dateTime = new Date(a[0], a[1]-1, a[2]).getTime();
        var d;
        if (dateToCalc) {
            var c = dateToCalc.split(/[^0-9]/);
            d = new Date(c[0], c[1]-1, c[2]).getTime()
        } else {
            // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime()
        }
        // Round down to floor so we don't add an extra day if session is 12+ hours into the day
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24))
    };

    this.validateIdentifier = function(sync, callback) {
      if (this.identifiers) return this.identifiers;
      var self = this;
       $.ajax ({
            type: "GET",
            url: "/gil-shortcut-alias-validation/" + $("#shortcut_alias").val(),
            async: sync? false : true
        }).done(function(data) {
          if (callback) callback(data);
        }).fail(function() {
          if (callback) callback();
        });

    };
    this.getOrgs = function(userId, sync, callback) {
        var self = this;
        $.ajax ({
            type: "GET",
            url: '/api/organization',
            async: sync? false : true
        }).done(function(data) {

            $("#fillOrgs").attr("userId", userId);

            OT.populateOrgsList(data.entry);
            OT.populateUI();
            if (callback) callback();

            $("#userOrgs input[name='organization']").each(function() {
                $(this).on("click", function() {

                    var userId = $("#fillOrgs").attr("userId");
                    var parentOrg = $(this).attr("data-parent-id");

                    if ($(this).prop("checked")){
                        if ($(this).attr("id") !== "noOrgs") {
                            //console.log("set no org here")
                            $("#noOrgs").prop('checked',false);

                        } else {
                            $("#userOrgs input[name='organization']").each(function() {
                                //console.log("in id: " + $(this).attr("id"))
                               if ($(this).attr("id") !== "noOrgs") {
                                    $(this).prop('checked',false);
                                };
                            });

                        };
                    };
                });
            });
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
           if (callback) callback();
        });
    },
    this.updateOrg = function(userId, callback) {

        var demoArray = {}, errorMessage = "";
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId,
            async: false
        }).done(function(data) {
            demoArray = data;
        }).fail(function() {
            errorMessage = "Error retrieving demographics information for user.";
        });
        var orgIDs = $("#userOrgs input[name='organization']:checked").map(function(){
            return { reference: "api/organization/"+$(this).val() };
        }).get();

        if (!hasValue(errorMessage)) {
          if (typeof orgIDs === 'undefined'){
              orgIDs = [0]  // special value for `none of the above`
          } else {
            var __roles =  [{'name': 'patient'}];
            //update user role if user has chosen an org
            $.ajax ({
              type: "PUT",
              url: '/api/user/'+userId+'/roles',
              contentType: "application/json; charset=utf-8",
              dataType: 'json',
              data: JSON.stringify({"roles": __roles})
            }).done(function(data) {

            }).fail(function(jhr) {
              errorMessage += (hasValue(errorMessage) ? "<br/>":"") + "Error occurred updating user role.";
            });
          };

          demoArray["careProvider"] = orgIDs;

          $.ajax ({
              type: "PUT",
              url: '/api/demographics/'+userId,
              contentType: "application/json; charset=utf-8",
              dataType: 'json',
              async: true,
              data: JSON.stringify(demoArray)
          }).done(function(data) {
              if (callback) callback(errorMessage);
          }).fail(function() {
              errorMessage += (hasValue(errorMessage) ? "<br/>":"") + "Error occurred updating user organization.";
              if (callback) callback(errorMessage);
          });
        } else {
          if(typeof callback != "undefined") callback(errorMessage);
        };

    },
    this.filterOrgs = function(leafOrgs) {
        //console.log(leafOrgs)
        if (!leafOrgs) return false;
        var self = this;

        $("input[name='organization']:checkbox").each(function() {
            if (! self.inArray($(this).val(), leafOrgs)) {
                $(this).hide();
                if (orgsList[$(this).val()] && orgsList[$(this).val()].children.length == 0) $(this).closest("label").hide();
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
                             };
                         });

                        if (!isVisible) {
                            $(this).hide();
                        } else allSubOrgsHidden = false;

                    });

                    if (allSubOrgsHidden) $(this).children("label").hide();

                } else {
                    var ip = $(this).find("input[name='organization']");
                    if (ip.length > 0) {
                        ip.each(function() {
                            if ($(this).is(":visible")) allChildrenHidden = false;
                        });
                    };
                };
            });
            if (allChildrenHidden) {
                $("#fillOrgs").find("legend[orgid='" + orgId + "']").hide();
            };

        });
    };

    this.findOrg = function(entry, orgId) {
        var org;
        if (entry && orgId) {
            entry.forEach(function(item) {
                if (!org) {
                    if (item.id == orgId) org = item;
                };
            });
        };
        return org;
    };
    this.getTopLevelOrgs = function() {
        if (TOP_LEVEL_ORGS.length == 0) {
            var topOrgs = $("#fillOrgs").find(input[name='organization'][parent_org='true']);
            if (topOrgs.length > 0) {
                topOrgs.each(function() {
                    TOP_LEVEL_ORGS.push[$(this).val()];
                });
            };
        };
        return TOP_LEVEL_ORGS;
    };

    this.populateOrgsList = function(items) {
        if (!items) return false;
        var entry = items, self = this, parentId;
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (!orgsList[parentId]) {
                    var o = self.findOrg(entry, parentId);
                    orgsList[parentId] = new OrgObj(o.id, o.name);
                };
                orgsList[parentId].children.push(new OrgObj(item.id, item.name, parentId));
                if (orgsList[item.id]) orgsList[item.id].parentOrgId = parentId;
                else orgsList[item.id] = new OrgObj(item.id, item.name, parentId);
            } else {
                if (!orgsList[item.id]) orgsList[item.id] = new OrgObj(item.id, item.name);
                if (item.id != 0) {
                    orgsList[item.id].isTopLevel = true;
                    TOP_LEVEL_ORGS.push(item.id);
                };
            };
        });
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (orgsList[item.id]) orgsList[item.id].parentOrgId = parentId;
            };
        });
        //console.log(orgsList)
        return orgsList;
    };

    this.populateUI = function() {
        var parentOrgsCt = 0, topLevelOrgs = this.getTopLevelOrgs();
        for (org in orgsList) {
            if (orgsList[org].isTopLevel && (orgsList[org].children.length > 0)) {
                $("#fillOrgs").append("<legend orgId='" + org + "'>"+orgsList[org].name+"</legend><input class='tnth-hide' type='checkbox' name='organization' parent_org=\"true\" org_name=\"" + orgsList[org].name + "\" id='" + orgsList[org].id + "_org' value='"+orgsList[org].id+"' />");
                parentOrgsCt++;
            }
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
                        '<input class="clinic" type="checkbox" name="organization" id="' +  item.id + '_org" value="'+
                        item.id +'"  ' +  (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") + '/><span>'+
                        item.name +
                        '</span></label>';

                     } else {
                        childClinic += '<label class="org-label">' +
                        '<input class="clinic" type="checkbox" name="organization" id="' +  item.id + '_org" value="'+
                        item.id +'"  ' +  (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") + '/><span>'+
                        item.name +
                        '</span></label>';
                    };

                    childClinic += '</div>';

                    if ($("#" + _parentOrgId + "_container").length > 0) $("#" + _parentOrgId + "_container").append(childClinic);
                    else $("#fillOrgs").append(childClinic);

                });
            };

            if (parentOrgsCt > 0 && orgsList[org].isTopLevel) $("#fillOrgs").append("<span class='divider'>&nbsp;</span>");
        };
    };
};

var OT = new OrgTool();

function handleNoOrgs(userId) {
      $(".intervention-link, a.decision-support-link").each(function() {
        var dm = /decision\s?support/gi;
        if (dm.test($(this).text()) || $(this).hasClass("decision-support-link")) {
            var hasSet = (typeof sessionStorage != "undefined") && sessionStorage.getItem("noOrgModalViewed");
            //allow modal to show once once action has been taken
            if (hasSet) return false;
            var self = this;
            $.ajax ({
                type: "GET",
                url: '/api/demographics/' + userId,
                async: false
            }).done(function(data) {
                //console.log(data)
                if (data && data.careProvider) {
                    $.each(data.careProvider,function(i,val){
                        var orgID = val.reference.split("/").pop();
                        if (parseInt(orgID) === 0) {
                          $(self).removeAttr("href");
                          $(self).on("click", function() {
                            $("figure.js-close-nav").trigger("click");
                            setTimeout('$("#modal-org").modal("show");', 0);
                          });
                          if (typeof sessionStorage != "undefined") {
                              sessionStorage.removeItem("decisionSupportInSession");
                          };
                        };
                    });
                };
            }).fail(function() {
               // console.log("Problem retrieving data from server.");
            });
        };
     });
  };

function updateOrgCallback(errorMessage) {
    if (!errorMessage) {
      $("#modal-org a.box-modal__close").trigger("click");
      loader(true);
      setTimeout("location.reload();", 1000);
      if (typeof sessionStorage != "undefined") {
        try {
          sessionStorage.setItem("noOrgModalViewed", "true");
        } catch(e) {

        };
      };
    } else {
      $("#modal-org-error").html(errorMessage);
    };
};



