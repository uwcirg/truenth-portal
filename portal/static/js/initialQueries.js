
(function() {

  function hasValue(val) {
    return String(val) !== "null" && String(val) !== "" && String(val) !== "undefined";
  };

  function disableHeaderFooterLinks() {
    var links = $("#tnthNavWrapper a, #homeFooter a").not("a[href*='logout']").not("a.required-link").not("a.home-link");
    links.addClass("disabled");
    links.prop("onclick",null).off("click");
    links.on("click", function(e) {
        e.preventDefault();
        return false;
    });
  };
  /*
   * helper class to keep track of missing fields based on required/needed core data
   */

  var FieldsChecker = function(
    userId,
    roleRequired,
    CONFIG_DEFAULT_CORE_DATA,
    CONFIG_REQUIRED_CORE_DATA,
    preselectClinic,
    dependencies) {

    this.__getDependency = function(key) {
      if (key && this.dependencies.hasOwnProperty(key)) {
        return this.dependencies[key];
      }
      else {
        //should show up in console
        throw new Error("Dependency with key value: " + key + " not found.");
      };
    };
    this.userId = userId;
    this.CONFIG_DEFAULT_CORE_DATA = CONFIG_DEFAULT_CORE_DATA;
    this.CONFIG_REQUIRED_CORE_DATA = CONFIG_REQUIRED_CORE_DATA;
    this.roleRequired = roleRequired;
    this.preselectClinic = preselectClinic;
    this.mainSections = {};
    this.defaultSections = {};
    this.incompleteFields = [];
    this.dependencies = dependencies || {};

  };

  FieldsChecker.prototype.init = function(callback) {
    var self = this;
    this.initConfig(function(data) {
      self.initSections();
      if (callback) {
        callback(data);
      };
    });
  };

  FieldsChecker.prototype.initSections = function() {
    var self = this;
    self.setSections();
    if (!self.getConfig()) {
        this.mainSections = this.defaultSections;
    }
    else {
      var defaultSections = this.defaultSections;
      for (var section in defaultSections) {
          if (defaultSections[section].required) {
            this.mainSections[section] = defaultSections[section];
          } else if (self.inConfig(defaultSections[section].config)) {
            this.mainSections[section] = defaultSections[section];
        };
      };
    };
  };

  FieldsChecker.prototype.setSections = function() {
      var preselectClinic = this.preselectClinic;
      var self = this;
      var i18next = this.__getDependency("i18next");
      var orgTool = this.__getDependency("orgTool");
      /*
       * main sections blueprint object, this will help keeping track of missing fields for each section
       *
       */
      this.defaultSections =  {
          "topTerms": {
                display: i18next.t("terms"),
                config: "website_terms_of_use,subject_website_consent,privacy_policy",
                subsections: {
                  "termsCheckbox": {
                      fields: [$("#topTerms [data-type='terms'][data-required='true']")]
                  }
                },
                handleIncomplete: function() {
                  $("#aboutForm").addClass("full-size");
                  $("#topTerms").removeClass("hide-terms").show();
                  if (window.performance) {
                    if (performance.navigation.type === 1) {
                      //page has been reloaded;
                      var agreedCheckboxes = $("#topTerms .terms-label:visible i");
                      if (agreedCheckboxes.length > 1) {
                          $("#termsReminderCheckboxText").text(i18next.t("You must agree to the terms and conditions by checking the provided checkboxes."));
                      };
                      if (agreedCheckboxes.length === 0) {
                        $("#termsText").addClass("agreed");
                      }
                      $("#termsReminderModal").modal("show");
                    };
                  };
                  setTimeout(function() { disableHeaderFooterLinks(); }, 1000);
                }
            },
            "demographicsContainer": {
                display: i18next.t("your information"),
                config: "name,dob,role",
                subsections:{
                "nameGroup": {
                  fields: [$("#firstname"), $("#lastname")]
                }
                ,
                "rolesGroup": {
                  fields: [$("input[name='user_type']")]
                }
                ,
                "bdGroup": {
                    fields: [$("#month"), $("#date"), $("#year")]
                  }
                }
            },
            "clinicalContainer": {
                display: i18next.t("your clinical profile"),
                config: "clinical,localized",
                subsections:{
                  "patientQ": {
                    fields: [$("input[name='biopsy']"), $("#biopsyDate"), $("input[name='pca_diag']"), $("input[name='pca_localized']"), $("input[name='tx']")]
                  }
                }
            },
            "orgsContainer": {
                display: i18next.t("your clinic"),
                config: "org",
                required: hasValue(preselectClinic) ? true: false,
                subsections:{
                  "clinics": {
                    fields: [$("#userOrgs input[name='organization']")]
                  }
                },
                handleIncomplete: function() {
                  if (hasValue(preselectClinic)) {
                      orgTool.handlePreSelectedClinic();
                      var __modal = orgTool.getConsentModal();
                      if (__modal) {
                          __modal.modal("show");
                      };
                    $("#orgsContainer").fadeIn(500).addClass("open");
                  } else {
                    $("#orgsContainer").fadeIn(500).addClass("open");
                  }
                }
          }
      };
  };

  FieldsChecker.prototype.initEvent = function(field) {
      if (field) {
        var subSectionId = field.subsectionId, self = this;
        var fields = field.elements;
        $(fields).each(function() {
          switch(subSectionId) {
            case "termsCheckbox":
              self.termsCheckboxEvent([$(this)]);
              break;
            case "nameGroup":
              self.nameGroupEvent([$(this)]);
              break;
            case "bdGroup":
              self.bdGroupEvent([$(this)]);
              break;
            case "rolesGroup":
              self.rolesGroupEvent([$(this)]);
              break;
            case "patientQ":
              self.patientQEvent([$(this)]);
              break;
            case "clinics":
              self.clinicsEvent([$(this)]);
              break;
          };
        });
      };
  };

  FieldsChecker.prototype.initConfig = function(callback) {
    var self = this, tnthAjax = self.__getDependency("tnthAjax");
    tnthAjax.getStillNeededCoreData(self.userId, true, function(data) {
      self.setConfig(self.roleRequired ? data : null);
      if (callback) {
        callback(data);
      };
    });
  };

  FieldsChecker.prototype.inConfig = function(configMatch, dataArray) {
      if (!hasValue(configMatch)) {
        return false;
      } else {
        if (!dataArray) {
          dataArray = this.CONFIG_REQUIRED_CORE_DATA;
        }
        if (dataArray) {
          if (dataArray.length === 0) {
            return false;
          }
          var found = false;
          var ma = configMatch.split(",");
          ma.forEach(function(item) {
            dataArray.forEach(function(v) {
              if (!found && v === item) {
               found = true;
               };
            });
          });
          return found;
        } else {
          return true;
        };
      };
  };

  FieldsChecker.prototype.getDefaultConfig = function() {
    return this.CONFIG_DEFAULT_CORE_DATA;
  };

  FieldsChecker.prototype.getConfig = function() {
    return this.CONFIG_REQUIRED_CORE_DATA;
  };

  FieldsChecker.prototype.setConfig = function(data) {
    if (data) {
      if (!data.error) {
        this.CONFIG_REQUIRED_CORE_DATA = data;
      };
    } else {
        this.CONFIG_REQUIRED_CORE_DATA = this.CONFIG_DEFAULT_CORE_DATA;
    };
  };

  FieldsChecker.prototype.getTotalSections = function() {
    /*** note counting all the default main sections to show progress for each**/
    var configData = this.getDefaultConfig();
    var self = this;
    if (configData) {
      return configData.length;
    } else {
      return Object.keys(this.defaultSections);
    };
  };

  FieldsChecker.prototype.getCompleteSections = function() {
    var ct = 0, self = this;
    for (var section in this.mainSections) {
        if (self.sectionCompleted(section)) {
          ct++;
        };
    };
    return ct;
  };

  FieldsChecker.prototype.constructProgressBar = function() {
    //don't construct progress bar when terms present
    if ($("#topTerms").length > 0 && !this.sectionCompleted("topTerms")) {
      return false;
    };
    var self = this;
    var totalSections = self.getTotalSections();

    if (totalSections > 1) {
        var availableSections = 0;
        if (self.defaultSections) {
          for (var section in self.defaultSections) {
              var active = self.sectionCompleted(section);
              $("#progressbar").append("<li sectionId='" + section + "'  " + (active? " class='active'": "") + ">" + self.defaultSections[section].display + "</li>");
              availableSections++;
          };
        };
        if (availableSections > 0) {
            var w = (1/availableSections) * 100;
            $("#progressbar li").each(function() {
                $(this).css("width", w + "%");
            });
            if (availableSections > 1) {
              $("#progressWrapper").show();
            };
        };
    } else {
      $("#progressWrapper").remove();
    };
  };

  FieldsChecker.prototype.setProgressBar = function (sectionId) {
    if (this.allFieldsCompleted()) {
      $("#progressWrapper").hide();
    } else {
      if (hasValue(sectionId)) {
        if (this.sectionCompleted(sectionId)) {
          $("#progressbar li[sectionId='" + sectionId + "']").addClass("active");
        } else {
          $("#progressbar li[sectionId='" + sectionId + "']").removeClass("active");
        };
      };
    };
  };

  FieldsChecker.prototype.getIncompleteFields = function() {
    return this.incompleteFields;
  };

  FieldsChecker.prototype.setIncompleteFields = function() {
    var self = this;
    if (self.mainSections) {
      var ms = self.mainSections;
      self.reset();
      for (var section in ms) {
        if (!self.sectionCompleted(section)) {
          for (var sectionId in ms[section].subsections) {
            var fields = ms[section].subsections[sectionId].fields;
            fields.forEach(function(field) {
            if (field.length > 0) {
                self.incompleteFields.push({"sectionId": section, "subsectionId": sectionId, "section": $("#"+ section), "elements":field});
              };
            });
          };
        };
      };
    };
  };

  FieldsChecker.prototype.reset = function() {
    this.incompleteFields = [];
  };

  FieldsChecker.prototype.sectionCompleted = function(sectionId) {
    var isComplete = true, isChecked = false;
    if (this.mainSections && this.mainSections[sectionId]) {
      //count skipped section as complete
      if ($("#" + sectionId).attr("skipped") === "true") {
        return true;
      };
      for (var id in (this.mainSections[sectionId]).subsections) {
        var fields = (this.mainSections[sectionId]).subsections[id].fields;
        if (fields) {
            fields.forEach(function(field) {
              if (field.length > 0 && (field.attr("skipped") !== "true")) {
                var type = field.attr("data-type") || field.attr("type");
                switch(String(type).toLowerCase()) {
                  case "checkbox":
                  case "radio":
                        isChecked = false;
                        field.each(function() {
                          if ($(this).is(":checked")) {
                            isChecked = true;
                          };
                          if (hasValue($(this).attr("data-require-validate"))) {
                            isComplete = false;
                          };
                        });
                        if (!(isChecked)) {
                          isComplete = false;
                        };
                        break;
                  case "select":
                      if (field.val() === "") {
                        isComplete = false;
                      }
                      break;
                  case "text":
                      if (field.val() === "") {
                        isComplete = false;
                      }
                      else if (!(field.get(0).validity.valid)) {
                        isComplete = false;
                      };
                      break;
                  case "terms":
                      var isAgreed = true;
                      field.each(function() {
                        if (hasValue($(this).attr("data-required")) && !($(this).attr("data-agree") === "true")) {
                          isAgreed = false;
                        };
                      });
                      if (!isAgreed) {
                        isComplete = false;
                      };
                      break;
                  };
                  if (hasValue(field.attr("data-require-validate"))) {
                    isComplete = false;
                  };
              };
          });
        };
      };
    };
    return isComplete;
  };

  FieldsChecker.prototype.allFieldsCompleted = function() {
    this.setIncompleteFields();
    var completed = (!hasValue($(".custom-error").text())) && this.incompleteFields.length === 0;
    return completed;
  };

  FieldsChecker.prototype.showAll = function() {
    var mainSections = this.mainSections;
    if (mainSections) {
      for (var sec in mainSections) {
        if (mainSections.hasOwnProperty(sec)) {
          var mf = $("#" + sec);
          if (mf.attr("skipped") === "true") {
            continue;
          };
          mf.fadeIn();
          for (var sectionId in mainSections[sec].subsections) {
            mainSections[sec].subsections[sectionId].fields.forEach(function(field) {
              if (field.attr("skipped") !== "true") {
                field.fadeIn();
              };
            });
          };
        };
      };
    };
  };

  FieldsChecker.prototype.continueToFinish = function() {
    this.setProgressBar();
    $("#buttonsContainer").addClass("continue");
    $("div.reg-complete-container").fadeIn();
    $("html, body").stop().animate({
      scrollTop: $("div.reg-complete-container").offset().top
    }, 2000);
    $("#next").attr("disabled", true).removeClass("open");
    $("#iqErrorMessage").text("");
    $("#updateProfile").removeAttr("disabled").addClass("open");
  };

  FieldsChecker.prototype.stopContinue = function(sectionId) {
    $("#buttonsContainer").removeClass("continue");
    $("#updateProfile").attr("disabled", true).removeClass("open");
    $("div.reg-complete-container").fadeOut();
    $("#next").attr("disabled", true).addClass("open");
    this.setProgressBar(sectionId);
  }

  FieldsChecker.prototype.continueToNext = function(sectionId) {
    this.setProgressBar(sectionId);
    $("#buttonsContainer").removeClass("continue");
    $("div.reg-complete-container").fadeOut();
    $("#next").removeAttr("disabled").addClass("open");
    if (!$("#next").isOnScreen()) {
      setTimeout(function() {
        $("html, body").stop().animate({
          scrollTop: $("#next").offset().top
        }, 1500);
      }(), 500);
    };
    $("#updateProfile").attr("disabled", true).removeClass("open");
  };


  FieldsChecker.prototype.getNext = function() {
    var found = false, self = this;
    for (var section in self.mainSections) {
      if (!found && !self.sectionCompleted(section)) {
          self.handleIncomplete(section);
          $("#" + section).fadeIn(500).addClass("open");
          self.stopContinue(section);
          found = true;
      };
    };
    if (!found) {
      self.continueToFinish();
    };
  };

  FieldsChecker.prototype.handleIncomplete = function(section) {
    if (this.mainSections[section] && this.mainSections[section].handleIncomplete) {
      this.mainSections[section].handleIncomplete();
    };
  };

  FieldsChecker.prototype.sectionsLoaded = function() {
    var self = this, isLoaded = true;
    for (var section in self.mainSections) {
      if (isLoaded) {
        for (var subsectionId in self.mainSections[section].subsections) {
          if (!$("#" + subsectionId).attr("loaded")) {
            isLoaded = false;
          };
        };
      };
    };
    return isLoaded;
  };
  FieldsChecker.prototype.getFieldEventType = function(field) {
    var triggerEvent = $(field).attr("data-trigger-event");
    if (!hasValue(triggerEvent)) {
      triggerEvent = ($(field).attr("type") === "text" ? "blur" : "click");
    };
    if ($(field).get(0).nodeName.toLowerCase() === "select") {
      triggerEvent = "change";
    };
    return triggerEvent;
  };

  FieldsChecker.prototype.initIncompleteFields = function() {
    var self = this;
    self.setIncompleteFields();
    var incompleteFields = self.getIncompleteFields();
    incompleteFields.forEach(function(field, index) {
      self.initEvent(field);
    });
    /************
      //debugging code
      //incompleteFields.forEach(function(field, index) {
      //    console.log(field.section.attr("id") + " " + field.elements.length);
      //    console.log(field.elements)
      //});
    ************/
  };

  FieldsChecker.prototype.onIncompleteFieldsDidInit = function() {

    var self = this;

    /****** prep work after initializing incomplete fields *****/
    /*****  set visuals e.g. top terms ************************/

    self.constructProgressBar();
    var i18next = self.__getDependency("i18next");
    var assembleContent = self.__getDependency("assembleContent");

    $("#queriesForm").validator().on("submit", function (e) {
      if (e.isDefaultPrevented()) {
        $("#iqErrorMessage").text(i18next.t("There's a problem with your submission. Please check your answers, then try again.  Make sure all required fields are completed and valid."));
      } else {
        $("#updateProfile").hide();
        $("#next").hide();
        $(".loading-message-indicator").show();
        setTimeout(function() {
          assembleContent.demo($("#iq_userId").val(),null, null, true);
        }, 250);
      };
    });

    /*** event for the next button ***/
    $("#next").on("click", function() {
        $(this).hide();
        $(".loading-message-indicator").show();
        setTimeout(function() { window.location.reload(); }, 100);
    });

    /*** event for the arrow in the header**/
    $("div.heading").on("click", function() {
       $("html, body").animate({
          scrollTop: $(this).next("div.content-body").children().first().offset().top
       }, 1000);
    });

    //if term of use form not present - need to show the form
    if ($("#topTerms").length === 0)  {
      $("#aboutForm").fadeIn();
      self.getNext();
      if ($("#aboutForm").length === 0 || self.allFieldsCompleted()) {
        self.continueToFinish();
      };
    } else {
      if (!self.sectionCompleted("topTerms")) {
        self.handleIncomplete("topTerms");
      } else {
        $("#aboutForm").removeClass("full-size");
        self.getNext();
        $("#aboutForm").fadeIn();
        if ($("#aboutForm").length === 0 || self.allFieldsCompleted()) {
          self.continueToFinish();
        };
      };
    };

    setTimeout(function() { $("#iqFooterWrapper").show(); }, 500);
  };

  FieldsChecker.prototype.termsCheckboxEvent = function(fields) {
    var __self = this;
    var userId = __self.userId;
    var tnthAjax = this.__getDependency("tnthAjax");
    var orgTool = this.__getDependency("orgTool");

    var termsEvent = function() {
      if ($(this).attr("data-agree") === "false") {
          var types = $(this).attr("data-tou-type");
          if (hasValue(types)) {
            var arrTypes = types.split(",");
            var dataUrl = $(this).attr("data-url");
            arrTypes.forEach(function(type) {
              var theTerms = {};
              theTerms["agreement_url"] = hasValue(dataUrl) ? dataUrl : $("#termsURL").data().url;
              theTerms["type"] = type;
              var org = $("#userOrgs input[name='organization']:checked"), userOrgId = "";
              /*** if UI for orgs is not present, need to get the user org from backend ***/
              if (org.length === 0) {
                $.ajax ({
                  type: "GET",
                  url: "/api/demographics/" + userId,
                  async: false
                }).done(function(data) {
                  if (data && data.careProvider) {
                    (data.careProvider).forEach(function(item) {
                      userOrgId = item.reference.split("/").pop();
                    });
                  }
                }).fail(function() {

                });
              } else {
                 userOrgId = org.val();
              };

              if (hasValue(userOrgId) && parseInt(userOrgId) !== 0) {
                var topOrg = orgTool.getTopLevelParentOrg(userOrgId);
                if (hasValue(topOrg)) {
                  theTerms["organization_id"] = topOrg;
                };
              };
              // Post terms agreement via API
              tnthAjax.postTerms(theTerms);
            });
          };

          // Update UI
          if (this.nodeName.toLowerCase() === "label"){
            $(this).find("i").removeClass("fa-square-o").addClass("fa-check-square-o");
          } else {
            $(this).closest("label").find("i").removeClass("fa-square-o").addClass("fa-check-square-o");
          };

          $(this).attr("data-agree","true");
        };

        if (__self.sectionCompleted("topTerms")) {
          $("#aboutForm").fadeIn();
        };
        if (__self.allFieldsCompleted()) {
          __self.continueToFinish();
        } else {
          __self.continueToNext("topTerms");
        };
    };

    /*
     * account for the fact that some terms items are hidden as child elements to a label
     */
    $("#topTerms label.terms-label").each(function() {
      $(this).on("click", function() {
        if ($(this).attr("data-required")) {
          termsEvent.apply(this);
        } else {
          $(this).find("[data-required]").each(function() {
            termsEvent.apply(this);
          });
        };
      });
    });


    fields.forEach(function(item){
      $(item).each(function() {
        $(this).on(__self.getFieldEventType(item), termsEvent);
      });
    });

    $("#topTerms .required-link").each(function() {
      $(this).on("click", function(e) {
        e.stopPropagation();
      });
    });
  };

  FieldsChecker.prototype.nameGroupEvent = function(fields) {
    var self = this, assembleContent = self.__getDependency("assembleContent");
    fields.forEach(function(item) {
        $(item).on(self.getFieldEventType(item), function() {
          if (self.allFieldsCompleted()) {
            self.continueToFinish();
          } else {
            if (self.sectionCompleted("demographicsContainer")) {
              self.continueToNext("demographicsContainer");
            } else {
              self.stopContinue("demographicsContainer");
            };
          };
        });
        $(item).on("blur", function() {
          if ($(this).val() !== "") {
            assembleContent.demo($("#iq_userId").val());
          };
        });
    });
  };

  FieldsChecker.prototype.bdGroupEvent = function(fields) {
    var self = this, tnthDates = this.__getDependency("tnthDates"), assembleContent = this.__getDependency("assembleContent");
    fields.forEach(function(item) {
      $(item).on(self.getFieldEventType(item), function() {
        var d = $("#date");
        var m = $("#month");
        var y = $("#year");
        if (d.val() !== "" && m.val() !== "" && y.val() !== "") {
          if (this.validity.valid) {
              var isValid = tnthDates.validateDateInputFields(m.val(), d.val(), y.val(), "errorbirthday");
              if (isValid) {
                $("#birthday").val(y.val()+"-"+m.val()+"-"+d.val());
                $("#errorbirthday").text("").hide();
                assembleContent.demo($("#iq_userId").val());
                if (self.allFieldsCompleted()) {
                   self.continueToFinish();
                } else {
                  if (self.sectionCompleted("demographicsContainer")) {
                    self.continueToNext("demographicsContainer");
                  };
                };
              } else {
                self.stopContinue("demographicsContainer");
              };
          } else {
            self.stopContinue("demographicsContainer");
          };
        } else {
          self.stopContinue("demographicsContainer");
        };
      });
    });
  };

  FieldsChecker.prototype.rolesGroupEvent = function(fields) {
    var self = this, tnthAjax = this.__getDependency("tnthAjax");
    fields.forEach(function(item){
      $(item).on("click", function() {
        var roles = [];
        var theVal = $(this).val();
        roles.push({name: theVal});
        var toSend = {"roles": roles};
        tnthAjax.putRoles(self.userId,toSend);

        if (theVal === "patient") {
            $("#clinicalContainer").attr("skipped", "false");
            $("#orgsContainer").attr("skipped", "false");
            $("#date").attr("required", "required").attr("skipped", "false");
            $("#month").attr("required", "required").attr("skipped", "false");
            $("#year").attr("required", "required").attr("skipped", "false");
            $(".bd-optional").hide();
        } else {
          // If partner, skip all questions
          if (theVal === "partner") {
            $("#clinicalContainer").attr("skipped", "true");
            $("#orgsContainer").attr("skipped", "true");
            $("#date").removeAttr("required").attr("skipped", "true");
            $("#month").removeAttr("required").attr("skipped", "true");
            $("#year").removeAttr("required").attr("skipped", "true");
            $(".bd-optional").show();
          };
        };

        if (self.allFieldsCompleted()) {
          self.continueToFinish();
        } else {
          if (self.sectionCompleted("demographicsContainer")) {
            self.continueToNext("demographicsContainer");
          } else {
            self.stopContinue("demographicsContainer");
          };
        };
      });
    });
  };

  FieldsChecker.prototype.patientQEvent = function(fields) {
    var self = this, userId = self.userId, tnthAjax = this.__getDependency("tnthAjax");
    fields.forEach(function(item){
        $(item).on("click", function() {
          var thisItem = $(this);
          var toCall = thisItem.attr("name") || thisItem.attr("data-name");
          // Get value from div - either true or false
          var toSend = (toCall === "biopsy" ? ($("#patientQ input[name='biopsy']:checked").val()) : thisItem.val());
          //NOTE: treatment is updated on the onclick event of the treatment question iteself, see initial queries macro for detail
          if (toCall !== "tx" && toCall !== "biopsy") {
            tnthAjax.postClinical(userId,toCall,toSend, $(this).attr("data-status"), false);
          };
          if (toSend === "true" || toCall ===  "pca_localized") {
            if (toCall === "biopsy") {
              $("#biopsyDate").attr("skipped", "false");
              if (toSend === "true") {
                ["pca_diag", "pca_localized", "tx"].forEach(function(fieldName) {
                  $("input[name='" + fieldName + "']").each(function() {
                      $(this).attr("skipped", "false");
                  });
                });
              };
              if ($("#biopsyDate").val() === "") {
                return true;
              } else {
                tnthAjax.postClinical(userId, toCall, toSend, "", false, {"issuedDate": $("#biopsyDate").val()});
              };
              if (self.sectionCompleted("clinicalContainer")) {
                return false;
              };
            };

            thisItem.parents(".pat-q").next().fadeIn();

            var nextRadio = thisItem.closest(".pat-q").next(".pat-q");
            var nextItem = nextRadio.length > 0 ? nextRadio : thisItem.parents(".pat-q").next();
            if (nextItem.length > 0) {
                var checkedRadio = nextItem.find("input[type='radio']:checked");
                if (!(checkedRadio.length > 0)) {
                  $("html, body").animate({
                    scrollTop: nextItem.offset().top
                  }, 1000);
                };
                nextItem.find("input[type='radio']").each(function() {
                  $(this).attr("skipped", "false");
                });
                thisItem.closest(".pat-q").nextAll().each(function() {
                    var dataTopic = $(this).attr("data-topic");
                    $(this).find("input[name='" + dataTopic + "']").each(function() {
                        $(this).attr("skipped", "false");
                    });
                });

            };

          } else {
            if (toCall === "biopsy") {
              tnthAjax.postClinical(self.userId, toCall, "false", $(this).attr("data-status"));
              $("#biopsyDate").attr("skipped", "true");

              ["pca_diag", "pca_localized", "tx"].forEach(function(fieldName) {
                  $("input[name='" + fieldName + "']").each(function() {
                      $(this).prop("checked", false);
                      $(this).attr("skipped", "true");
                  });
              });
              if ($("input[name='pca_diag']").length > 0) {
                tnthAjax.putClinical(userId,"pca_diag","false");
              };
              if ($("input[name='pca_localized']").length > 0) {
                tnthAjax.putClinical(userId,"pca_localized","false");
              };

              if ($("input[name='tx']").length > 0) {
                tnthAjax.deleteTreatment(userId);
              };
            } else if (toCall === "pca_diag") {
              ["pca_localized", "tx"].forEach(function(fieldName) {
                  $("input[name='" + fieldName + "']").each(function() {
                      $(this).prop("checked", false);
                      $(this).attr("skipped", "true");
                  });
              });
              if ($("input[name='pca_localized']").length > 0) {
                tnthAjax.putClinical(userId,"pca_localized","false");
              };
              if ($("input[name='tx']").length > 0) {
                tnthAjax.deleteTreatment(userId);
              };
            }
            thisItem.parents(".pat-q").nextAll().fadeOut();
          };

          if (self.allFieldsCompleted()) {
            self.continueToFinish();
          } else {
            if (self.sectionCompleted("clinicalContainer")) {
              self.continueToNext("clinicalContainer");
            }
            else {
              self.stopContinue("clinicalContainer");
            };
          };

        });
    });
  };

  FieldsChecker.prototype.clinicsEvent = function(fields) {
    var self = this;
    fields.forEach(function(item) {
      $(item).on("click", function() {
        if ($(this).prop("checked")) {
          var parentOrg = $(this).attr("data-parent-id");
          var m = $("#" + parentOrg + "_consentModal");
          var dm = $("#" + parentOrg + "_defaultConsentModal");
          if ($("#fillOrgs").attr("patient_view") && m.length > 0 && $(this).val() != "0") {
            //do nothing
          } else if ($("#fillOrgs").attr("patient_view") && dm.length > 0 ) {
            //do nothing
          }
          else {
            if (self.allFieldsCompleted()) {
              self.continueToFinish();
            } else {
              if (self.sectionCompleted("orgsContainer")) {
                self.continueToNext("orgsContainer");
              } else {
                self.stopContinue("orgsContainer");
              };
            };
          };
        };
      });
    });

     /*** event for consent popups **/
    $("#consentContainer .modal, #defaultConsentContainer .modal").each(function() {
      $(this).on("hidden.bs.modal", function() {
        if ($(this).find("input[name='toConsent']:checked").length > 0) {
          $("#userOrgs input[name='organization']").each(function() {
            $(this).removeAttr("data-require-validate");
          });
          if (self.allFieldsCompleted()) {
            self.continueToFinish();
          } else {
            if (self.sectionCompleted("orgsContainer")) {
              self.continueToNext("orgsContainer");
            } else {
              self.stopContinue("orgsContainer");
            };
          };
        };
      });
    });
  };
  window.FieldsChecker = FieldsChecker;
})();





