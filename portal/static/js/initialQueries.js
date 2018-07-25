(function() { /*global $ hasValue disableHeaderFooterLinks __convertToNumericField*/
    var FieldsChecker = function(dependencies) { //helper class to keep track of missing fields based on required/needed core data
        this.__getDependency = function(key) {
            if (key && this.dependencies.hasOwnProperty(key)) {
                return this.dependencies[key];
            } else {
                //should show up in console
                throw new Error("Dependency with key value: " + key + " not found.");
            }
        };
        this.userId = null;
        this.roleRequired = false;
        this.userRoles = [];
        this.CONFIG_DEFAULT_CORE_DATA = null;
        this.CONFIG_REQUIRED_CORE_DATA = null;
        this.preselectClinic = "";
        this.mainSections = {};
        this.defaultSections = {};
        this.incompleteFields = [];
        this.dependencies = dependencies || {};
        this.orgTool = null;

    };

    FieldsChecker.prototype.init = function(callback) {
        var self = this;
        this.setUserId(function() {
            if (!self.userId) {
                alert("User id is required");
                return false;
            }
            self.initConfig(function(data) {
                self.preselectClinic = $("#preselectClinic").val();
                self.initSections();
                self.initSectionData(data);
                if (callback) {
                    callback(data);
                }
            });
        });
    };

    FieldsChecker.prototype.setUserId = function(callback) {
        var self = this, tnthAjax = this.__getDependency("tnthAjax");
        callback = callback || function() {};
        self.userId = $("#iq_userId").val(); //set in template, check this first as API can return error
        if (self.userId) {
            callback();
            return;
        }
        tnthAjax.getCurrentUser(function(data) {
            if (data && data.id) {
                self.userId = data.id;
            }
            callback();
        });
    };

    FieldsChecker.prototype.getOrgTool = function() {
        if (!this.orgTool) {
            this.orgTool = this.__getDependency("orgTool");
            this.orgTool.init();
        }
        return this.orgTool;
    };

    FieldsChecker.prototype.initSectionData = function(data) {
        var self = this, sections = self.getSections();
        for (var section in sections) {
            if (self.inConfig(sections[section].config, data)) {
                self.initData(section);
            }
        }
    };

    FieldsChecker.prototype.initData = function(section) {
        if (this.mainSections[section] && this.mainSections[section].initData) {
            this.mainSections[section].initData();
        }
    };

    FieldsChecker.prototype.getSections = function() {
        var sections = this.defaultSections;
        if (Object.keys(this.mainSections).length > 0) {
            sections = this.mainSections;
        }
        return sections;
    };

    FieldsChecker.prototype.initSections = function() {
        var self = this;
        self.setSections();
        if (!self.getConfig()) {
            this.mainSections = this.defaultSections;
        } else {
            var defaultSections = this.defaultSections;
            for (var section in defaultSections) {
                if (defaultSections[section].required) {
                    this.mainSections[section] = defaultSections[section];
                } else if (self.inConfig(defaultSections[section].config)) {
                    this.mainSections[section] = defaultSections[section];
                }
            }
        }
    };

    FieldsChecker.prototype.setSections = function() {
        var preselectClinic = this.preselectClinic, self = this, i18next = this.__getDependency("i18next");
        var tnthAjax = this.__getDependency("tnthAjax");
        this.defaultSections = { //main sections blueprint object, this will help keeping track of missing fields for each section
            "topTerms": {
                display: i18next.t("terms"),
                config: "website_terms_of_use,subject_website_consent,privacy_policy",
                subsections: {
                    "termsCheckbox": {
                        fields: ["#topTerms [data-type='terms'][data-required='true']"]
                    }
                },
                initData: function() {
                    tnthAjax.getTerms(self.userId, false, false, function(data) {
                        self.updateTerms(data);
                        $("#termsCheckbox").attr("loaded", "true");
                    }, {
                        "all": true
                    });
                    tnthAjax.getTermsUrl();
                },
                handleIncomplete: function() {
                    $("#aboutForm").addClass("full-size");
                    $("#topTerms").removeClass("hide-terms").show();
                    if (!$("#termsText").hasClass("agreed")) {
                        if (window.performance) {
                            if (performance.navigation.type === 1) {
                                //page has been reloaded;
                                var agreedCheckboxes = $("#topTerms [data-required][data-agree='false']");
                                if (agreedCheckboxes.length > 1) {
                                    $("#termsReminderCheckboxText").text(i18next.t("You must agree to the terms and conditions by checking the provided checkboxes."));
                                }
                                if (agreedCheckboxes.length === 0) {
                                    $("#termsText").addClass("agreed");
                                }
                                $("#termsReminderModal").modal("show");
                            }
                        }
                    } else {
                        $("#aboutForm").removeClass("tnth-hide");
                        self.continueToNext();
                    }
                    setTimeout(function() {disableHeaderFooterLinks();}, 1000);
                }
            },
            "demographicsContainer": {
                display: i18next.t("your information"),
                config: "name,dob,role",
                subsections: {
                    "nameGroup": {fields: ["#firstname", "#lastname"]},
                    "rolesGroup": {fields: ["input[name='user_type']"]},
                    "bdGroup": {fields: ["#month", "#date", "#year"]}
                },
                initData: function() {
                    tnthAjax.getDemo(self.userId, {useWorker:true}, function() {
                        $("#nameGroup").attr("loaded", "true");
                        $("#rolesGroup").attr("loaded", "true");
                        $("#bdGroup").attr("loaded", "true");
                    });
                    __convertToNumericField($("#date, #year"));
                }
            },
            "clinicalContainer": {
                display: i18next.t("your clinical profile"),
                config: "clinical,localized",
                subsections: {
                    "patientQ": {
                        fields: ["input[name='biopsy']", "#biopsyDate", "input[name='pca_diag']", "input[name='pca_localized']", "input[name='tx']"]
                    }
                },
                initData: function() {
                    tnthAjax.getTreatment(self.userId, {useWorker:true}, function() {
                        tnthAjax.getClinical(self.userId, {useWorker:true}, function() {
                            $("#patientQ").attr("loaded", "true");
                        });
                    });
                }
            },
            "orgsContainer": {
                display: i18next.t("your clinic"),
                config: "org",
                required: hasValue(preselectClinic) ? true : false,
                subsections: {
                    "clinics": {
                        fields: ["#userOrgs input[name='organization']"]
                    }
                },
                initData: function() {
                    if (!hasValue($("#iqPatientEditable").val())) { //for patient, clinic is drawn in orgs state selector template
                        tnthAjax.getOrgs(self.userId, {sync: true}, function() {
                            var userOrgs = $("#userOrgs input[name='organization']").not("[parent_org]");
                            if (userOrgs.length === 0) {
                                userOrgs = $("#userOrgs input[name='organization']");
                            }
                            var checkedOrgs = {};
                            userOrgs.each(function() {
                                if ($(this).prop("checked")) {
                                    checkedOrgs[$(this).val()] = true;
                                }
                                $(this).attr("type", "radio");
                                if (checkedOrgs[$(this).val()]) {
                                    $(this).prop("checked", true);
                                }
                            });
                            $("#clinics").attr("loaded", true);
                        });
                    }
                },
                handleIncomplete: function() {
                    if (hasValue(preselectClinic)) {
                        self.handlePreSelectedClinic();
                        var __modal = self.getConsentModal();
                        if (__modal) {
                            __modal.modal("show");
                        }
                        $("#orgsContainer").fadeIn(500).addClass("open");
                    } else {
                        $("#orgsContainer").fadeIn(500).addClass("open");
                    }
                }
            }
        };
    };

    FieldsChecker.prototype.postDemoData = function() {
        var demoArray = {}, tnthAjax = this.__getDependency("tnthAjax");
        demoArray.resourceType = "Patient";
        var fname = $("input[name=firstname]").val(), lname = $("input[name=lastname]").val();
        demoArray.name = {"given": $.trim(fname), "family": $.trim(lname)};
        var y = $("#year").val(), m = $("#month").val(), d = $("#date").val();
        if (y && m && d) {
            demoArray.birthDate = y + "-" + m + "-" + d;
        }
        tnthAjax.putDemo(this.userId, demoArray);
    };

    FieldsChecker.prototype.initEvent = function(field) {
        if (field) {
            var subSectionId = field.subsectionId,
                self = this;
            var fields = field.elements;
            var events = {
                "termsCheckbox": function(o) { self.termsCheckboxEvent(o); },
                "nameGroup": function(o) { self.nameGroupEvent(o); },
                "rolesGroup": function(o) { self.rolesGroupEvent(o); },
                "bdGroup": function(o) { self.bdGroupEvent(o); },
                "patientQ": function(o) { self.patientQEvent(o); },
                "clinics": function(o) { self.clinicsEvent(o); }
            };
            $(fields).each(function() {
                if (events[subSectionId]) {
                    events[subSectionId]([$(this)]);
                } else {
                    return true;
                }
            });
        }
    };

    FieldsChecker.prototype.setUserRoles = function() {
        var self = this, tnthAjax = self.__getDependency("tnthAjax");
        tnthAjax.getRoles(this.userId, function(data) {
            if (data.roles) {
                self.userRoles = data.roles.map(function(item) {
                    return item.name;
                });
            }
            self.roleRequired = self.userRoles.indexOf("patient") !== -1 || self.userRoles.indexOf("staff") !== -1 || self.userRoles.indexOf("staff_admin") !== -1;
        }, {sync: true});
    };

    FieldsChecker.prototype.initConfig = function(callback) {
        var self = this, tnthAjax = self.__getDependency("tnthAjax");
        tnthAjax.getStillNeededCoreData(self.userId, true, function(data) {
            self.setUserRoles();
            self.setConfig(self.roleRequired ? data : null, callback);
        });
    };

    FieldsChecker.prototype.inConfig = function(configMatch, dataArray) {
        if (!hasValue(configMatch)) {
            return false;
        } else {
            if (!dataArray) {
                dataArray = this.CONFIG_REQUIRED_CORE_DATA;
            }
            if (!dataArray || dataArray.length === 0) { return false; }
            var found = false;
            var ma = configMatch.split(",");
            ma.forEach(function(item) {
                if (found) { return true; } /* IMPORTANT, immediately return true. without checking this item, this is in the context of the loop, the sequence matters here, loop still continues*/
                found = dataArray.indexOf(item) !== -1;
            });
            return found;
        }
    };

    FieldsChecker.prototype.getDefaultConfig = function() {
        var self = this, tnthAjax = this.__getDependency("tnthAjax");
        if (!this.CONFIG_DEFAULT_CORE_DATA) {
            tnthAjax.getConfigurationByKey("REQUIRED_CORE_DATA", self.userId, {
                sync: true
            }, function(data) {
                if (!data.error) {
                    if (data.REQUIRED_CORE_DATA) {
                        self.CONFIG_DEFAULT_CORE_DATA = data.REQUIRED_CORE_DATA;
                    }
                }
            });
        }
        return this.CONFIG_DEFAULT_CORE_DATA;
    };

    FieldsChecker.prototype.getConfig = function() {
        return this.CONFIG_REQUIRED_CORE_DATA;
    };

    FieldsChecker.prototype.setConfig = function(data, callback) {
        callback = callback || function() {};
        var tnthAjax = this.__getDependency("tnthAjax");
        if (data) {
            if (!data.error) {
                this.CONFIG_REQUIRED_CORE_DATA = data;
            }
        }
        if (!this.CONFIG_REQUIRED_CORE_DATA) { //get default required core data
            var self = this;
            tnthAjax.getConfigurationByKey("REQUIRED_CORE_DATA", this.userId, {
                sync: true
            }, function(data) {
                if (!data.error) {
                    if (data.REQUIRED_CORE_DATA) {
                        self.CONFIG_REQUIRED_CORE_DATA = data.REQUIRED_CORE_DATA;
                    }
                }
                callback();
            });
        } else {
            callback();
        }
    };

    FieldsChecker.prototype.getTotalSections = function() {
        /*** note counting all the default main sections to show progress for each**/
        var configData = this.getDefaultConfig();
        if (configData) {
            return configData.length;
        } else {
            return Object.keys(this.defaultSections);
        }
    };

    FieldsChecker.prototype.getCompleteSections = function() {
        var ct = 0,
            self = this;
        for (var section in this.mainSections) {
            if (self.sectionCompleted(section)) {
                ct++;
            }
        }
        return ct;
    };

    FieldsChecker.prototype.constructProgressBar = function() {
        //don't construct progress bar when terms present
        if ($("#topTerms").length > 0 && !this.sectionCompleted("topTerms")) {
            return false;
        }
        var self = this;
        var totalSections = self.getTotalSections();

        if (totalSections > 1) {
            var availableSections = 0;
            if (self.defaultSections) {
                for (var section in self.defaultSections) {
                    if (self.defaultSections.hasOwnProperty(section)) {
                        var active = self.sectionCompleted(section);
                        $("#progressbar").append("<li sectionId='" + section + "'  " + (active ? " class='active'" : "") + ">" + self.defaultSections[section].display + "</li>");
                        availableSections++;
                    }
                }
            }
            if (availableSections > 0) {
                var w = (1 / availableSections) * 100;
                $("#progressbar li").each(function() {
                    $(this).css("width", w + "%");
                });
                if (availableSections > 1) {
                    $("#progressWrapper").show();
                }
            }
        } else {
            $("#progressWrapper").remove();
        }
    };

    FieldsChecker.prototype.setProgressBar = function(sectionId) {
        if (this.allFieldsCompleted()) {
            $("#progressWrapper").hide();
        } else {
            if (hasValue(sectionId)) {
                if (this.sectionCompleted(sectionId)) {
                    $("#progressbar li[sectionId='" + sectionId + "']").addClass("active");
                } else {
                    $("#progressbar li[sectionId='" + sectionId + "']").removeClass("active");
                }
            }
        }
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
                            field = $(field);
                            if (field.length > 0) {
                                self.incompleteFields.push({
                                    "sectionId": section,
                                    "subsectionId": sectionId,
                                    "section": $("#" + section),
                                    "elements": field
                                });
                            }
                        });
                    }
                }
            }
        }
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
            }
            for (var id in (this.mainSections[sectionId]).subsections) {
                var fields = (this.mainSections[sectionId]).subsections[id].fields;
                if (!isComplete || !fields) {return isComplete; }
                fields.forEach(function(field) {
                    field = $(field);
                    if (field.length === 0 || field.attr("skipped") === "true") { return true; }
                    var type = field.attr("data-type") || field.attr("type");
                    switch (String(type).toLowerCase()) {
                    case "checkbox":
                    case "radio":
                        isChecked = false;
                        field.each(function() {
                            if ($(this).is(":checked")) {
                                isChecked = true;
                            }
                            if (hasValue($(this).attr("data-require-validate"))) {
                                isComplete = false;
                            }
                        });
                        if (!(isChecked)) {
                            isComplete = false;
                        }
                        break;
                    case "select":
                        isComplete = field.val() !== "";
                        break;
                    case "text":
                        isComplete = (field.val() !== "") && (field.get(0).validity.valid);
                        break;
                    case "terms":
                        var isAgreed = true;
                        field.each(function() {
                            if (hasValue($(this).attr("data-required")) && !($(this).attr("data-agree") === "true")) {
                                isAgreed = false;
                            }
                        });
                        isComplete = isAgreed;
                        break;
                    }
                    if (hasValue(field.attr("data-require-validate"))) {
                        isComplete = false;
                    }
                });
            }
        }
        return isComplete;
    };

    FieldsChecker.prototype.allFieldsCompleted = function() {
        this.setIncompleteFields();
        var completed = (!hasValue($(".custom-error").text())) && this.incompleteFields.length === 0;
        return completed;
    };

    FieldsChecker.prototype.continueToFinish = function() {
        if ($("div.reg-complete-container").hasClass("inactive")) {
            return false;
        }
        this.setProgressBar();
        $("#buttonsContainer").addClass("continue");
        $("div.reg-complete-container").fadeIn();
        $("html, body").stop().animate({
            scrollTop: $("div.reg-complete-container").offset().top
        }, 1500);
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
    };

    FieldsChecker.prototype.continueToNext = function(sectionId) {
        if (sectionId) {
            this.setProgressBar(sectionId);
        }
        $("#buttonsContainer").removeClass("continue");
        $("div.reg-complete-container").fadeOut();
        $("#next").removeAttr("disabled").addClass("open");
        if (!$("#next").isOnScreen()) {
            setTimeout(function() {
                $("html, body").stop().animate({
                    scrollTop: $("#next").offset().top
                }, 1500);
            }(), 500);
        }
        $("#updateProfile").attr("disabled", true).removeClass("open");
    };


    FieldsChecker.prototype.getNext = function() {
        var found = false,
            self = this;
        for (var section in self.mainSections) {
            if (!found && !self.sectionCompleted(section)) {
                self.handleIncomplete(section);
                $("#" + section).fadeIn(500).addClass("open");
                self.stopContinue(section);
                found = true;
            }
        }
        if (!found) {
            self.continueToFinish();
        }
    };

    FieldsChecker.prototype.handleIncomplete = function(section) {
        if (this.mainSections[section] && this.mainSections[section].handleIncomplete) {
            this.mainSections[section].handleIncomplete();
        }
    };

    FieldsChecker.prototype.sectionsLoaded = function() {
        var self = this, isLoaded = true, subsectionId;
        //check all
        for (var section in self.mainSections) {
            if (!self.mainSections.hasOwnProperty(section)) {
                return false;
            }
            for (subsectionId in self.mainSections[section].subsections) {
                if (isLoaded && !$("#" + subsectionId).attr("loaded")) {
                    isLoaded = false;
                }
            }
        }
        return isLoaded;
    };
    FieldsChecker.prototype.getFieldEventType = function(field) {
        var triggerEvent = $(field).attr("data-trigger-event");
        if (!hasValue(triggerEvent)) {
            triggerEvent = ($(field).attr("type") === "text" ? "blur" : "click");
        }
        if ($(field).get(0).nodeName.toLowerCase() === "select") {
            triggerEvent = "change";
        }
        return triggerEvent;
    };

    FieldsChecker.prototype.initIncompleteFields = function() {
        var self = this;
        self.setIncompleteFields();
        var incompleteFields = self.getIncompleteFields();
        incompleteFields.forEach(function(field) {
            self.initEvent(field);
        });
    };

    FieldsChecker.prototype.onIncompleteFieldsDidInit = function() {
        var self = this;
        /****** prep work after initializing incomplete fields -set visuals e.g. top terms ************************/
        self.constructProgressBar();
        var i18next = self.__getDependency("i18next");
        $("#queriesForm").validator().on("submit", function(e) {
            if (e.isDefaultPrevented()) {
                $("#iqErrorMessage").text(i18next.t("There's a problem with your submission. Please check your answers, then try again.  Make sure all required fields are completed and valid."));
            } else {
                $("#updateProfile").hide();
                $("#next").hide();
                $(".loading-message-indicator").show();
                setTimeout(function() {
                    self.postDemoData();
                }, 250);
            }
        });
        /*** event for the next button ***/
        $("#next").on("click", function() {
            $(this).hide();
            $(".loading-message-indicator").show();
            setTimeout(function() {
                window.location.reload();
            }, 500);
        });
        /*** event for the arrow in the header**/
        $("div.heading").on("click", function() {
            $("html, body").animate({
                scrollTop: $(this).next("div.content-body").children().first().offset().top
            }, 1000);
        });
        $(window).bind("scroll mousedown mousewheel keyup", function() {
            if ($("html, body").is(":animated")) {
                $("html, body").stop(true, true);
            }
        });
        //if term of use form not present - need to show the form
        if ($("#topTerms").length === 0) {
            $("#aboutForm").fadeIn();
            self.getNext();
            if ($("#aboutForm").length === 0 || self.allFieldsCompleted()) {
                self.continueToFinish();
            }
        } else {
            if (!self.sectionCompleted("topTerms")) {
                self.handleIncomplete("topTerms");
            } else {
                $("#aboutForm").removeClass("full-size");
                self.getNext();
                $("#aboutForm").fadeIn();
                if ($("#aboutForm").length === 0 || self.allFieldsCompleted()) {
                    self.continueToFinish();
                }
            }
        }
        setTimeout(function() {
            $("#iqFooterWrapper").show();
        }, 500);
    };

    FieldsChecker.prototype.handlePostEvent = function(sectionId) {
        if (sectionId) {
            if (this.allFieldsCompleted()) {
                this.continueToFinish();
            } else {
                if (this.sectionCompleted(sectionId)) {
                    this.continueToNext(sectionId);
                } else {
                    this.stopContinue(sectionId);
                }
            }
        }
    };

    FieldsChecker.prototype.updateTerms = function(data) {
        function typeInTous(type, status) {
            var found = false, isActive = String(status) === "active";
            (data.tous).forEach(function(item) {
                if (!found &&
                    ($.trim(item.type) === $.trim(type)) &&
                    (String($.trim(item.active)) === String(isActive))) {
                    found = true;
                }
            });
            return found;
        }
        if (data.tous) {
            $("#termsCheckbox label.terms-label").each(function() {
                var item_found = 0;
                var self = $(this);
                self.find("[data-type='terms']").each(function() {
                    var type = $(this).attr("data-tou-type");
                    if (typeInTous(type, "active")) {
                        item_found++;
                        $("#termsCheckbox [data-tou-type='" + type + "']").attr("data-agree", "true"); //set the data-agree attribute for the corresponding consent item

                    }
                    if (typeInTous(type, "inactive")) {
                        self.attr("data-reconsent", "true");
                        self.closest("#termsCheckbox").attr("data-reconsent", "true");
                    }
                });
                if (item_found > 0) {
                    if (self.find("[data-agree='false']").length === 0) { // make sure that all items are agreed upon before checking the box
                        self.find("i").removeClass("fa-square-o").addClass("fa-check-square-o").addClass("edit-view");
                        var vs = self.find(".display-view");
                        if (vs.length > 0) {
                            self.show();
                            vs.show();
                            (self.find(".edit-view")).each(function() {
                                $(this).hide();
                            });
                        }
                    }
                    self.show().removeClass("tnth-hide");
                }
            });
        }
    };

    FieldsChecker.prototype.termsCheckboxEvent = function(fields) {
        var __self = this;
        var userId = __self.userId, tnthAjax = this.__getDependency("tnthAjax"), orgTool = this.getOrgTool();
        var termsEvent = function() {
            if ($(this).attr("data-agree") === "false") {
                var types = $(this).attr("data-tou-type");
                if (hasValue(types)) {
                    var arrTypes = types.split(","), dataUrl = $(this).attr("data-url");
                    arrTypes.forEach(function(type) {
                        if ($("#termsCheckbox [data-agree='true'][data-tou-type='" + type + "']").length > 0) { //if already agreed, don't post again
                            return true;
                        }
                        var theTerms = {};
                        theTerms["agreement_url"] = hasValue(dataUrl) ? dataUrl : $("#termsURL").data().url;
                        theTerms["type"] = type;
                        var org = $("#userOrgs input[name='organization']:checked"),
                            userOrgId = org.val();
                        /*** if UI for orgs is not present, need to get the user org from backend ***/
                        if (!userOrgId) {
                            $.ajax({
                                type: "GET",
                                url: "/api/demographics/" + userId,
                                async: false
                            }).done(function(data) {
                                if (data && data.careProvider) {
                                    (data.careProvider).forEach(function(item) {
                                        if (!userOrgId) {
                                            userOrgId = item.reference.split("/").pop();
                                            return true;
                                        }
                                    });
                                }
                            }).fail(function() {});
                        }
                        if (hasValue(userOrgId) && parseInt(userOrgId) !== 0 && !isNaN(parseInt(userOrgId))) {
                            var topOrg = orgTool.getTopLevelParentOrg(userOrgId);
                            if (hasValue(topOrg)) {
                                theTerms["organization_id"] = topOrg;
                            }
                        }
                        tnthAjax.postTerms(theTerms); // Post terms agreement via API
                    });
                }
                // Update UI
                if (this.nodeName.toLowerCase() === "label") {
                    $(this).find("i").removeClass("fa-square-o").addClass("fa-check-square-o");
                } else {
                    $(this).closest("label").find("i").removeClass("fa-square-o").addClass("fa-check-square-o");
                }
                //adding css rule here so the checkbox won't be hidden on click
                $(this).attr("current", "true");
                $(this).attr("data-agree", "true");

                var coreTypes = [], parentCoreType = $(this).attr("data-core-data-type");
                if (hasValue(parentCoreType)) {
                    coreTypes.push(parentCoreType);
                }
                $(this).closest("label").find("[data-core-data-type]").each(function() {
                    var coreDataType = $(this).attr("data-core-data-type");
                    if($.inArray(coreDataType, coreTypes) === -1) {
                        coreTypes.push(coreDataType);
                    }
                });
                if (coreTypes.length > 0) { //need to delete notification for each corresponding coredata terms type once user has agreed
                    coreTypes.forEach(function(type) {
                        var notificationEntry = $("#notificationBanner [data-name='" + type + "_update']");
                        if (notificationEntry.length > 0) {
                            Global.deleteNotification($("#notificationUserId").val(), notificationEntry.attr("data-id")); /*global Global */
                        }
                    });
                }
            }

            if (__self.sectionCompleted("topTerms")) {
                $("#aboutForm").fadeIn();
            }
            if (__self.allFieldsCompleted()) {
                __self.continueToFinish();
            } else {
                __self.continueToNext("topTerms");
            }
        };
        $("#topTerms label.terms-label").each(function() { //account for the fact that some terms items are hidden as child elements to a label
            $(this).on("click", function() {
                if ($(this).attr("data-required")) {
                    termsEvent.apply(this);
                } else {
                    $(this).find("[data-required]").each(function() {
                        termsEvent.apply(this);
                    });
                }
            });
        });
        fields.forEach(function(item) {
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
        var self = this;
        fields.forEach(function(item) {
            $(item).on(self.getFieldEventType(item), function() {
                self.handlePostEvent("demographicsContainer");
            });
            $(item).on("blur", function() {
                if ($(this).val() !== "") {
                    self.postDemoData();
                }
            });
        });
    };

    FieldsChecker.prototype.bdGroupEvent = function(fields) {
        var self = this, tnthDates = this.__getDependency("tnthDates");
        fields.forEach(function(item) {
            $(item).on(self.getFieldEventType(item), function() {
                var d = $("#date"), m = $("#month"), y = $("#year");
                var isValid = tnthDates.validateDateInputFields(m, d, y, "errorbirthday");
                if (isValid) {
                    $("#birthday").val(y.val() + "-" + m.val() + "-" + d.val());
                    $("#errorbirthday").text("").hide();
                    self.postDemoData();
                    self.handlePostEvent("demographicsContainer");
                } else {
                    self.stopContinue("demographicsContainer");
                }
            });
        });
    };

    FieldsChecker.prototype.rolesGroupEvent = function(fields) {
        var self = this, tnthAjax = this.__getDependency("tnthAjax");
        fields.forEach(function(item) {
            $(item).on("click", function() {
                var roles = [], theVal = $(this).val();
                roles.push({name: theVal});
                tnthAjax.putRoles(self.userId,{"roles": roles});
                if (theVal === "patient") {
                    $("#clinicalContainer").attr("skipped", "false");
                    $("#orgsContainer").attr("skipped", "false");
                    $("#date").attr("required", "required").attr("skipped", "false");
                    $("#month").attr("required", "required").attr("skipped", "false");
                    $("#year").attr("required", "required").attr("skipped", "false");
                    $(".bd-optional").hide();
                } else {
                    if (theVal === "partner") { // If partner, skip all questions
                        $("#clinicalContainer").attr("skipped", "true");
                        $("#orgsContainer").attr("skipped", "true");
                        $("#date").removeAttr("required").attr("skipped", "true");
                        $("#month").removeAttr("required").attr("skipped", "true");
                        $("#year").removeAttr("required").attr("skipped", "true");
                        $(".bd-optional").show();
                    }
                }
                self.handlePostEvent("demographicsContainer");
            });
        });
    };

    FieldsChecker.prototype.patientQEvent = function(fields) {
        var self = this;
        fields.forEach(function(item) {
            $(item).on("click", function() {
                var thisItem = $(this);
                var toCall = thisItem.attr("name") || thisItem.attr("data-name");
                var toSend = (toCall === "biopsy" ? ($("#patientQ input[name='biopsy']:checked").val()) : thisItem.val());
                if (toSend === "true" || toCall === "pca_localized") {
                    if (toCall === "biopsy" && !$("#biopsyDate").val()) {
                        return true;
                    }
                    thisItem.parents(".pat-q").next().fadeIn();
                    var nextRadio = thisItem.closest(".pat-q").next(".pat-q");
                    var nextItem = nextRadio.length > 0 ? nextRadio : thisItem.parents(".pat-q").next();
                    if (nextItem.length > 0) {
                        var checkedRadio = nextItem.find("input[type='radio']:checked");
                        if (!(checkedRadio.length > 0)) {
                            $("html, body").animate({scrollTop: nextItem.offset().top}, 1000);
                        }
                        nextItem.find("input[type='radio']").each(function() {
                            $(this).attr("skipped", "false");
                        });
                        thisItem.closest(".pat-q").nextAll().each(function() {
                            var dataTopic = $(this).attr("data-topic");
                            $(this).find("input[name='" + dataTopic + "']").each(function() {
                                $(this).attr("skipped", "false");
                            });
                        });
                    }
                } else {
                    thisItem.parents(".pat-q").nextAll().fadeOut();
                }
                self.handlePostEvent("clinicalContainer");

            });
        });
    };
    FieldsChecker.prototype.getConsentModal = function(parentOrg) {
        var orgTool = this.getOrgTool();
        parentOrg = parentOrg || orgTool.getElementParentOrg(orgTool.getSelectedOrg());
        if (parentOrg) {
            var __modal = $("#" + parentOrg + "_consentModal");
            if (__modal.length > 0) {
                return __modal;
            } else {
                var __defaultModal = $("#" + parentOrg + "_defaultConsentModal");
                if (__defaultModal.length > 0) {
                    return __defaultModal;
                }
            }
            return false;
        } else {
            return false;
        }
    };
    FieldsChecker.prototype.handlePreSelectedClinic = function() {
        var preselectClinic = $("#preselectClinic").val(), orgTool = this.getOrgTool();
        if (preselectClinic) {
            var ob = $("#userOrgs input[value='" + preselectClinic + "']");
            if (ob.length > 0) {
                ob.prop("checked", true);
                var parentOrg = orgTool.getElementParentOrg(orgTool.getSelectedOrg());
                var __modal = this.getConsentModal(parentOrg);
                if (__modal) {
                    ob.attr("data-require-validate", "true");
                }
                var stateContainer = ob.closest(".state-container");
                var st = stateContainer.attr("state");
                if (stateContainer.length > 0 && st) {
                    $("#stateSelector").find("option[value='" + st + "']").prop("selected", true).val(st);
                    stateContainer.show();
                }
            }
        }
    };

    FieldsChecker.prototype.clinicsEvent = function(fields) {
        var self = this;
        fields.forEach(function(item) {
            $(item).on("click", function() {
                if ($(this).prop("checked")) {
                    var parentOrg = $(this).attr("data-parent-id"), m = $("#" + parentOrg + "_consentModal"), dm = $("#" + parentOrg + "_defaultConsentModal");
                    if ($("#fillOrgs").attr("patient_view") && m.length > 0 && parseInt($(this).val()) !== 0) { //do nothing
                        return true;
                    } else if ($("#fillOrgs").attr("patient_view") && dm.length > 0) { //do nothing
                        return true;
                    } else {
                        self.continueToFinish();
                    }
                }
            });
        });
        /*** event for consent popups **/
        $("#consentContainer .modal, #defaultConsentContainer .modal").each(function() {
            $(this).on("hidden.bs.modal", function() {
                if ($(this).find("input[name='toConsent']:checked").length > 0) {
                    $("#userOrgs input[name='organization']").each(function() {
                        $(this).removeAttr("data-require-validate");
                    });
                    self.continueToFinish();
                }
            });
        });
    };
    window.FieldsChecker = FieldsChecker;

    $(document).ready(function() {
        /*
         * the flow here :
         * get still needed core data
         * populate all required fields
         * get incomplete fields thereafter
         * note: need to delay gathering incomplete fields to allow fields to be render
         */
        if ($("#aboutForm").length > 0 || $("#topTerms").length > 0) { /*global i18next, tnthAjax, OrgTool, tnthDates*/
            var fc = new window.FieldsChecker({
                i18next: i18next,
                tnthAjax: tnthAjax,
                orgTool: new OrgTool(),
                tnthDates: tnthDates
            });
            fc.init(function() {
                fc.startTime = new Date();
                DELAY_LOADING = true; /*global DELAY_LOADING */
                fc.intervalId = setInterval(function() {
                    fc.endTime = new Date();
                    var elapsedTime = fc.endTime - fc.startTime;
                    elapsedTime /= 1000;
                    if (fc.sectionsLoaded() || elapsedTime >= 3) {
                        setTimeout(function() {
                            fc.initIncompleteFields();
                            fc.onIncompleteFieldsDidInit();
                            DELAY_LOADING = false;
                            showMain(); /* global showMain */
                            hideLoader(true); /* global hideLoader */
                        }, 300);
                        fc.startTime = 0;
                        fc.endTime = 0;
                        clearInterval(fc.intervalId);
                    }
                }, 100);
            });
        }
    });
})();

