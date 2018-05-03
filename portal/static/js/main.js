/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/
var DELAY_LOADING = false;
var SYSTEM_IDENTIFIER_ENUM = {
    "external_study_id": "http://us.truenth.org/identity-codes/external-study-id",
    "external_site_id": "http://us.truenth.org/identity-codes/external-site-id",
    "practice_region": "http://us.truenth.org/identity-codes/practice-region",
    "race": "http://hl7.org/fhir/StructureDefinition/us-core-race",
    "ethnicity": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
    "indigenous": "http://us.truenth.org/fhir/StructureDefinition/AU-NHHD-METeOR-id-291036",
    "timezone": "http://hl7.org/fhir/StructureDefinition/user-timezone",
    "language": "http://hl7.org/fhir/valueset/languages",
    "shortname": "http://us.truenth.org/identity-codes/shortname"
};
var assembleContent = {
    "demo": function(userId, onProfile, targetField, sync, callback) {
        var demoArray = {};
        demoArray.resourceType = "Patient";
        var fname = $("input[name=firstname]").val(), lname = $("input[name=lastname]").val();

        demoArray.name = {
            "given": $.trim(fname),
            "family": $.trim(lname)
        };

        var bdFieldVal = "", y = $("#year").val(), m = $("#month").val(), d = $("#date").val();
        if (y && m && d) {
            bdFieldVal = y + "-" + m + "-" + d;
        }
        if (bdFieldVal) {
            demoArray.birthDate = bdFieldVal;
        }

        var preselectClinic = $("#preselectClinic").val();
        if (preselectClinic) {
            var parentOrg = $("#userOrgs input[name='organization'][value='" + preselectClinic + "']").attr("data-parent-id");
            if (!parentOrg) {
                parentOrg = preselectClinic;
            }
            if (tnthAjax.hasConsent(userId, parentOrg)) {
                demoArray.careProvider = [{reference: "api/organization/" + preselectClinic}];
            }
        } else {

            if ($("#userOrgs input[name='organization']").length > 0) {
                var orgIDs;
                orgIDs = $("#userOrgs input[name='organization']").map(function() {
                    if ($(this).prop("checked")) {
                        return {reference: "api/organization/" + $(this).val()};
                    }
                }).get();

                if (orgIDs) {
                    if (orgIDs.length > 0) {
                        demoArray.careProvider = orgIDs;
                    }
                }
            }

            /**** dealing with the scenario where user can be affiliated with top level org e.g. TrueNTH Global Registry, IRONMAN, via direct database addition **/
            var topLevelOrgs = $("#fillOrgs legend[data-checked]");
            if (topLevelOrgs.length > 0) {
                topLevelOrgs.each(function() {
                    var tOrg = $(this).attr("orgid");
                    if (tOrg) {
                        if (!demoArray.careProvider) {
                            demoArray.careProvider = [];
                        }
                        demoArray.careProvider.push({reference: "api/organization/" + tOrg});
                    }
                });
            }
        }

        if (!demoArray.careProvider || (demoArray.careProvider && demoArray.careProvider.length === 0)) { //don't update org to none if there are top level org affiliation above
            if ($("#aboutForm").length === 0) {
                demoArray.careProvider = [{reference: "api/organization/" + 0}];
            }
        }

        if ($("#deathDate").val()) {
            demoArray.deceasedDateTime = $("#deathDate").val();
        }

        if (!$("#deathDate").val()) {
            if ($("#boolDeath").length > 0) {
                if ($("#boolDeath").prop("checked")) {
                    demoArray.deceasedBoolean = true;
                } else {
                    demoArray.deceasedBoolean = false;
                }
            }
        }

        if (onProfile) {
            // Grab profile field values - looks for regular and hidden, can be checkbox or radio
            var e = $("#userEthnicity"), r = $("#userRace"), i = $("#userIndigenousStatus"), tz = $("#profileTimeZone");
            var ethnicityIDs, raceIDs, indigenousIDs, tzID;

            demoArray.extension = [];

            if (e.length > 0) {
                ethnicityIDs = $("#userEthnicity input:checked").map(function() {
                    return {code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity"};
                }).get();

                if (ethnicityIDs) {
                    demoArray.extension.push({
                        "url": SYSTEM_IDENTIFIER_ENUM.ethnicity,
                        "valueCodeableConcept": {
                            "coding": ethnicityIDs
                        }
                    });
                }
            }
            if (r.length > 0) {
                raceIDs = $("#userRace input:checkbox:checked").map(function() {
                    return {code: $(this).val(),system: "http://hl7.org/fhir/v3/Race"};
                }).get();
                if (raceIDs) {
                    demoArray.extension.push({
                        "url": SYSTEM_IDENTIFIER_ENUM.race,
                        "valueCodeableConcept": {
                            "coding": raceIDs
                        }
                    });
                }
            }

            if (i.length > 0) {
                indigenousIDs = $("#userIndigenousStatus input[type='radio']:checked").map(function() {
                    return {
                        code: $(this).val(),
                        system: SYSTEM_IDENTIFIER_ENUM.indigenous
                    };
                }).get();
                if (indigenousIDs) {
                    demoArray.extension.push({
                        "url": SYSTEM_IDENTIFIER_ENUM.indigenous,
                        "valueCodeableConcept": {
                            "coding": indigenousIDs
                        }
                    });
                }
            }

            if ($("#locale").length > 0 && $("#locale").find("option:selected").length > 0) {
                var selectedLocale = $("#locale").find("option:selected");
                demoArray.communication = [{
                    "language": {
                        "coding": [{
                            "code": selectedLocale.val(),
                            "display": selectedLocale.text(),
                            "system": "urn:ietf:bcp:47"
                        }]
                    }
                }];
            }

            if (tz.length > 0) {
                tzID = $("#profileTimeZone option:selected").val();
                if (tzID) {
                    demoArray.extension.push({
                        timezone: tzID,
                        url: SYSTEM_IDENTIFIER_ENUM.timezone
                    });
                }
            }

            var studyIdField = $("#profileStudyId"), siteIdField = $("#profileSiteId");
            var studyId = studyIdField.val(); //studyId field is only present in Eproms
            var siteId = siteIdField.val(); //siteId field is only present in Truenth
            var identifiers = [];
            $.ajax({ //get current identifier(s)
                type: "GET",
                url: "/api/demographics/" + userId,
                async: false
            }).done(function(data) {
                if (data && data.identifier) {
                    (data.identifier).forEach(function(identifier) {
                        identifiers.push(identifier);
                    });
                }
            }).fail(function(xhr) {
                tnthAjax.reportError(userId, "api/demographics" + userId, xhr.responseText);
            });

            identifiers = $.grep(identifiers, function(identifier) { //this will save study Id or site Id only if each has a value otherwise if each is empty, it will be purged from the identifiers that had older value of each
                return identifier.system !== SYSTEM_IDENTIFIER_ENUM.external_study_id &&
                    identifier.system !== SYSTEM_IDENTIFIER_ENUM.external_site_id;
            });

            studyId = $.trim(studyId);
            if (studyId) {
                var studyIdObj = {
                    system: SYSTEM_IDENTIFIER_ENUM.external_study_id,
                    use: "secondary",
                    value: studyId
                };
                identifiers.push(studyIdObj);
            }

            siteId = $.trim(siteId);
            if (siteId) {
                var siteIdObj = {
                    system: SYSTEM_IDENTIFIER_ENUM.external_site_id,
                    use: "secondary",
                    value: siteId
                };
                identifiers.push(siteIdObj);
            }

            if (identifiers.length > 0) {
                demoArray.identifier = identifiers;
            }

            demoArray.gender = $("input[name=sex]:checked").val();
            demoArray.telecom = [];

            var emailVal = $("input[name=email]").val();
            if ($.trim(emailVal)) {
                demoArray.telecom.push({
                    "system": "email",
                    "value": $.trim(emailVal)
                });
            } else {
                demoArray.telecom.push({ //'__no_email__'
                    "system": "email",
                    "value": "__no_email__"
                });
            }

            var phone = $.trim($("input[name=phone]").val());
            if (phone) {
                demoArray.telecom.push({"system": "phone","use": "mobile","value": phone});
            }
            var altphone = $.trim($("input[name=altPhone]").val());
            if (altphone) {
                demoArray.telecom.push({
                    "system": "phone",
                    "use": "home",
                    "value": altphone
                });
            }
        }
        if (callback) {
            callback(demoArray);
        }
        tnthAjax.putDemo(userId, demoArray, targetField, sync);
    },
    "coreData": function(userId) {
        var demoArray = {};
        demoArray.resourceType = "Patient";
        demoArray.extension = [];
        if ($("#userEthnicity").length > 0) {
            var ethnicityIDs = $("#userEthnicity input:checked").map(function() {
                return {
                    code: $(this).val(),
                    system: "http://hl7.org/fhir/v3/Ethnicity"
                };
            }).get();
            demoArray.extension.push({
                "url": SYSTEM_IDENTIFIER_ENUM.ethnicity,
                "valueCodeableConcept": {
                    "coding": ethnicityIDs
                }
            });
        }
        if ($("#userRace").length > 0) {
            var raceIDs = $("#userRace input:checkbox:checked").map(function() {
                return {
                    code: $(this).val(),
                    system: "http://hl7.org/fhir/v3/Race"
                };
            }).get();
            demoArray.extension.push({
                "url": SYSTEM_IDENTIFIER_ENUM.race,
                "valueCodeableConcept": {
                    "coding": raceIDs
                }
            });
        }
        tnthAjax.putDemo(userId, demoArray);
    }
};

var OrgObj = function(orgId, orgName, parentOrg) {
    this.id = orgId;
    this.name = orgName;
    this.children = [];
    this.parentOrgId = parentOrg;
    this.isTopLevel = false;
    this.language = null;
    this.extension = [];
};

var OrgTool = function() {
    this.TOP_LEVEL_ORGS = [];
    this.orgsList = {};
    this.initialized = false;
};

OrgTool.prototype.init = function(callback) {
    var self = this;
    callback = callback || function() {};
    if (sessionStorage.orgsData) {
        var orgsData = JSON.parse(sessionStorage.orgsData);
        self.populateOrgsList(orgsData);
        callback(orgsData);
    } else {
        $.ajax({
            type: "GET",
            url: "/api/organization",
            async: false
        }).done(function(data) {
            if (data && data.entry) {
                self.populateOrgsList(data.entry);
                sessionStorage.setItem("orgsData", JSON.stringify(data.entry));
                callback(data.entry);
            }
        }).fail(function(xhr) {
            callback({"error": xhr.responseText});
            tnthAjax.sendError(xhr, "/api/organization");
        });
    }
};

OrgTool.prototype.onLoaded = function(userId, doPopulateUI) {
    if (userId) {
        this.setUserId(userId);
    }
    if (doPopulateUI) {
        this.populateUI();
    }
    $("#userOrgs input[name='organization']").each(function() {
        $(this).prop("checked", false);
    });
    this.handlePreSelectedClinic();
    this.handleEvent();
    $("#clinics").attr("loaded", true);
};

OrgTool.prototype.setUserId = function(userId) {
    $("#fillOrgs").attr("userId", userId);
};

OrgTool.prototype.getUserId = function() {
    return $("#fillOrgs").attr("userId");
};

OrgTool.prototype.inArray = function(n, array) {
    if (n && array && Array.isArray(array)) {
        var found = false;
        for (var index = 0; !found && index < array.length; index++) {
            if (array[index] == n) {
                found = true;
            }
        }
        return found;
    } else return false;
};
OrgTool.prototype.getElementParentOrg = function(o) {
    var parentOrg;
    if (o) {
        parentOrg = $(o).attr("data-parent-id");
        if (!parentOrg) {
            parentOrg = $(o).closest(".org-container[data-parent-id]").attr("data-parent-id");
        }
    }
    return parentOrg;
};
OrgTool.prototype.getTopLevelOrgs = function() {
    var ml = this.getOrgsList(), orgList = [];
    for (var org in ml) {
        if (ml[org].isTopLevel) {
            orgList.push(org);
        }
    }
    return orgList;
};
OrgTool.prototype.getOrgsList = function() {
    return this.orgsList;
};
OrgTool.prototype.filterOrgs = function(leafOrgs) {
    if (!leafOrgs) {
        return false;
    }
    if (leafOrgs.length === 0) {
        return false;
    }
    var self = this;
    $("input[name='organization']").each(function() {
        if (!self.inArray($(this).val(), leafOrgs)) {
            $(this).hide();
            if (self.orgsList[$(this).val()]) {
                var l;
                if (self.orgsList[$(this).val()].children.length === 0) {
                    l = $(this).closest("label");
                    l.hide();
                } else {
                    l = $(this).closest("label");
                    l.addClass("data-display-only");
                }
            }
        }
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
                        if ($(this).is(":visible") || $(this).css("display") !== "none") {
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
                        if ($(this).is(":visible") || $(this).css("display") != "none") allChildrenHidden = false;
                    });
                }
            }
        });
        if (allChildrenHidden) {
            $("#fillOrgs").find("legend[orgid='" + orgId + "']").hide();
        }
    });
};
OrgTool.prototype.findOrg = function(entry, orgId) {
    var org;
    if (entry && orgId) {
        entry.forEach(function(item) {
            if (!org) {
                if (parseInt(item.id) === parseInt(orgId)) {
                    org = item;
                }
            }
        });
    }
    return org;
};
OrgTool.prototype.populateOrgsList = function(items) {
    var entry = items, self = this, parentId, orgsList = {};
    if (Object.keys(this.orgsList).length === 0) {
        if (!items) {
            return false;
        }
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (!orgsList[parentId]) {
                    var o = self.findOrg(entry, parentId);
                    orgsList[parentId] = new OrgObj(o.id, o.name);
                }
                orgsList[parentId].children.push(new OrgObj(item.id, item.name, parentId));
                if (orgsList[item.id]) orgsList[item.id].parentOrgId = parentId;
                else orgsList[item.id] = new OrgObj(item.id, item.name, parentId);
            } else {
                if (!orgsList[item.id]) orgsList[item.id] = new OrgObj(item.id, item.name);
                if (item.id != 0) {
                    orgsList[item.id].isTopLevel = true;
                    self.TOP_LEVEL_ORGS.push(item.id);
                }
            }
            if (item.extension) orgsList[item.id].extension = item.extension;
            if (item.language) orgsList[item.id].language = item.language;
            if (item.identifier) {
                orgsList[item.id].identifier = item.identifier;
                (item.identifier).forEach(function(identifier) {
                    if (identifier.system === SYSTEM_IDENTIFIER_ENUM.shortname) {
                        orgsList[item.id].shortname = identifier.value;
                    }
                });
            }

        });
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (orgsList[item.id]) orgsList[item.id].parentOrgId = parentId;
            }
        });
        if (items.length > 0) {
            this.initialized = true;
        }
        this.orgsList = orgsList;
    }
    return orgsList;
};
OrgTool.prototype.getShortName = function(orgId) {
    var shortName = "", orgsList = this.getOrgsList();
    if (orgId) {
        if (orgsList[orgId] && orgsList[orgId].shortname) {
            shortName = orgsList[orgId].shortname;
        }
    }
    return shortName;
};
OrgTool.prototype.populateUI = function() {
    var self = this, container = $("#fillOrgs"), orgsList = this.orgsList, parentContent = "";

    function getState(item) {
        var s = "",
            found = false;
        if (item.identifier) {
            (item.identifier).forEach(function(i) {
                if (!found && (i.system === SYSTEM_IDENTIFIER_ENUM.practice_region && i.value)) {
                    s = (i.value).split(":")[1];
                    found = true;
                }
            });
        }
        return s;
    }

    var keys = Object.keys(orgsList), parentOrgsArray = [];
    keys = keys.sort();
    keys.forEach(function(org) { //draw parent orgs first
        if (orgsList[org].isTopLevel) {
            parentOrgsArray.push(org);
        }
    });

    parentOrgsArray = parentOrgsArray.sort(function(a, b) { //sort parent orgs by name
        var orgA = orgsList[a],
            orgB = orgsList[b];
        if (orgA.name < orgB.name) return -1;
        if (orgA.name > orgB.name) return 1;
        return 0;
    });

    parentOrgsArray.forEach(function(org) {
        if (orgsList[org].children.length > 0) {
            if ($("#userOrgs legend[orgId='" + org + "']").length == 0) {
                parentContent = "<div id='{{orgId}}_container' class='parent-org-container'><legend orgId='{{orgId}}'>{{orgName}}</legend>" +
                    "<input class='tnth-hide' type='checkbox' name='organization' parent_org='true' data-org-name='{{orgName}}' data-short-name='{{shortName}}' id='{{orgId}}_org' state='{{state}}' value='{{orgId}}' /></div>";
                parentContent = parentContent.replace(/\{\{orgId\}\}/g, org)
                    .replace(/\{\{shortName\}\}/g, (orgsList[org].shortname || orgsList[org].name))
                    .replace(/\{\{orgName\}\}/g, i18next.t(orgsList[org].name))
                    .replace(/\{\{state\}\}/g, getState(orgsList[org]));
                container.append(parentContent);
            }
        } else {
            if ($("#userOrgs label[id='org-label-" + org + "']").length == 0) {
                parentContent = "<div id='{{orgId}}_container' class='parent-org-container parent-singleton'><label id='org-label-{{orgId}}' class='org-label'>" +
                    "<input class='clinic' type='checkbox' name='organization' parent_org='true' id='{{orgId}}_org' state='{{state}}' value='{{orgId}}' " +
                    "data-parent-id='{{orgId}}'  data-org-name='{{orgName}}' data-short-name='{{shortName}}' data-parent-name='{{orgName}}'/><span>{{orgName}}</span></label></div>";
                parentContent = parentContent.replace(/\{\{orgId\}\}/g, org)
                    .replace(/\{\{shortName\}\}/g, (orgsList[org].shortname || orgsList[org].name))
                    .replace(/\{\{orgName\}\}/g, i18next.t(orgsList[org].name))
                    .replace(/\{\{state\}\}/g, getState(orgsList[org]));
                container.append(parentContent);
            }
        }
    });

    keys.forEach(function(org) { //draw child orgs
        if (orgsList[org].children.length > 0) { // Fill in each child clinic
            var childClinic = "";
            var items = orgsList[org].children.sort(function(a, b) { // sort child clinic in alphabetical order
                if (a.name < b.name) return -1;
                if (a.name > b.name) return 1;
                return 0;
            });
            items.forEach(function(item) {
                var _parentOrgId = item.parentOrgId;
                var _parentOrg = orgsList[_parentOrgId];
                var _isTopLevel = _parentOrg ? _parentOrg.isTopLevel : false;
                var state = getState(orgsList[_parentOrgId]);
                var topLevelOrgId = self.getTopLevelParentOrg(item.id);

                if ($("#fillOrgs input[name='organization'][value='" + item.id + "']").length > 0) {
                    return true;
                }
                childClinic = "<div id='{{itemId}}_container' {{dataAttributes}} class='indent org-container {{containerClass}}'>" +
                    "<label id='org-label-{{itemId}}' class='org-label {{textClasses}}'>" +
                    "<input class='clinic' type='checkbox' name='organization' id='{{itemId}}_org' data-org-name='{{itemName}}' data-short-name='{{shortName}}' state='{{state}}' value='{{itemId}}' {{dataAttributes}} />" +
                    "<span>{{itemName}}</span>" +
                    "</label>" +
                    "</div>";
                childClinic = childClinic.replace(/\{\{itemId\}\}/g, item.id)
                    .replace(/\{\{itemName\}\}/g, item.name)
                    .replace(/\{\{shortName\}\}/g, (item.shortname || item.name))
                    .replace(/\{\{state\}\}/g, state ? state : "")
                    .replace(/\{\{dataAttributes\}\}/g, (_isTopLevel ? (' data-parent-id="' + _parentOrgId + '"  data-parent-name="' + _parentOrg.name + '" ') : (' data-parent-id="' + topLevelOrgId + '"  data-parent-name="' + orgsList[topLevelOrgId].name + '" ')))
                    .replace("{{containerClass}}", (orgsList[item.id].children.length > 0 ? (_isTopLevel ? "sub-org-container" : "") : ""))
                    .replace(/\{\{textClasses\}\}/g, (orgsList[item.id].children.length > 0 ? (_isTopLevel ? "text-muted" : "text-muter") : ""));

                if ($("#" + _parentOrgId + "_container").length > 0) {
                    $("#" + _parentOrgId + "_container").append(childClinic);
                } else {
                    container.append(childClinic);
                }
            });
        }
    });
    if (!container.text()) {
        container.html(i18next.t("No organizations available"));
    }
};
OrgTool.prototype.getDefaultModal = function(o) {
    if (!o) {
        return false;
    }
    var self = this, orgsList = self.getOrgsList(), orgId = self.getElementParentOrg(o),
        orgName = (orgsList[orgId] && orgsList[orgId].shortname) ? orgsList[orgId].shortname : ($(o).attr("data-parent-name") || $(o).closest("label").text());
    var title = i18next.t("Consent to share information");
    var consentText = i18next.t("I consent to sharing information with <span class='consent-clinic-name'>{orgName}</span>.".replace("{orgName}", orgName));
    if (orgId && $("#" + orgId + "_defaultConsentModal").length === 0) {
        var s = '<div class="modal fade" id="{orgId}_defaultConsentModal" tabindex="-1" role="dialog" aria-labelledby="{orgId}_defaultConsentModal">' +
            '<div class="modal-dialog" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header">' +
            '<button type="button" class="close" data-dismiss="modal" aria-label="{close}">' + "<span aria-hidden='true'>&times;</span></button>" +
            '<h4 class="modal-title">{title}</h4>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="content-loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i></div>' +
            '<div class="main-content tnth-hide">' +
            '<p>{consentText}</p>' +
            '<div id="{orgId}defaultConsentAgreementRadioList" class="profile-radio-list">' +
            '<label class="radio-inline">' +
            '<input type="radio" name="toConsent" id="{orgId}_consent_yes" data-org="{orgId}" value="yes"/>{yes}</label>' +
            '<br/>' +
            '<label class="radio-inline">' +
            '<input type="radio" name="toConsent" id="{orgId}_consent_no" data-org="{orgId}"  value="no"/>{no}</label>' +
            '</div>' +
            '</div>' +
            '<div id="{orgId}_consentAgreementMessage" class="error-message"></div>' +
            '</div>' +
            '<br/>' +
            '<div class="modal-footer" >' +
            '<div id="{orgId}_loader" class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i></div>' +
            '<button type="button" class="btn btn-default btn-consent-close" data-org="{orgId}" data-dismiss="modal" aria-label="{close}">{close}</button>' +
            '</div></div></div></div>';
        s = s.replace(/\{orgId\}/g, orgId)
            .replace(/\{close\}/g, i18next.t("Close"))
            .replace(/\{yes\}/g, i18next.t("Yes"))
            .replace(/\{no\}/g, i18next.t("No"))
            .replace(/\{title\}/g, title)
            .replace(/\{consentText\}/g, consentText);
        if ($("#defaultConsentContainer").length === 0) {
            $("body").append("<div id='defaultConsentContainer'></div>");
        }
        $("#defaultConsentContainer").append(s);
        $("#" + orgId + "_defaultConsentModal input[name='toConsent']").each(function() {
            $(this).on("click", function(e) {
                e.stopPropagation();
                var orgId = $(this).attr("data-org");
                var userId = self.getUserId();
                $("#" + orgId + "_defaultConsentModal button.btn-consent-close, #" + orgId + "_defaultConsentModal button[data-dismiss]").attr("disabled", true);
                $("#" + orgId + "_loader").show();
                if ($(this).val() == "yes") {
                    setTimeout("tnthAjax.setDefaultConsent(" + userId + "," + orgId + ");", 100);
                } else {
                    tnthAjax.deleteConsent(userId, {"org": orgId});
                    setTimeout(function() {
                        tnthAjax.removeObsoleteConsent();
                    }, 100);
                }
                setTimeout(function() {
                    tnthAjax.reloadConsentList(self.userId);
                }, 500);
                setTimeout(function() {
                    $(".modal").modal("hide");
                }, 250);
            });
        });
        $(document).delegate("#" + orgId + "_defaultConsentModal button[data-dismiss]", "click", function(e) {
            e.preventDefault();
            e.stopPropagation();
            setTimeout(function() {
                location.reload();
            }, 10);
        });
        $("#" + orgId + "_defaultConsentModal").on("hidden.bs.modal", function() {
            if ($(this).find("input[name='toConsent']:checked").length > 0) {
                $("#userOrgs input[name='organization']").each(function() {
                    $(this).removeAttr("data-require-validate");
                });
                var userId = self.getUserId();
                assembleContent.demo(userId, true, $("#userOrgs input[name='organization']:checked"), true);
            }
        }).on("shown.bs.modal", function() {
            var checkedOrg = $("#userOrgs input[name='organization']:checked");
            var shortName = self.getShortName(checkedOrg.val());
            if (shortName) {
                $(this).find(".consent-clinic-name").text(i18next.t(shortName));
            }
            $(this).find("input[name='toConsent']").each(function() {
                $(this).prop("checked", false);
            });
            $(this).find("button.btn-consent-close, button[data-dismiss]").attr("disabled", false).show();
            $(this).find(".content-loading-message-indicator").fadeOut(50, function() {
                $("#" + orgId + "_defaultConsentModal .main-content").removeClass("tnth-hide");
            });
            $(this).find(".loading-message-indicator").hide();
        });
    }
    return $("#" + orgId + "_defaultConsentModal");
};
OrgTool.prototype.handlePreSelectedClinic = function() {
    var preselectClinic = $("#preselectClinic").val();
    if (preselectClinic) {
        var ob = $("#userOrgs input[value='" + preselectClinic + "']");
        var self = this;
        if (ob.length > 0) {
            ob.prop("checked", true);
            var parentOrg = this.getElementParentOrg(this.getSelectedOrg());
            var userId = this.getUserId();
            if (!tnthAjax.hasConsent(userId, parentOrg)) {
                var __modal = self.getConsentModal();
                if (__modal) {
                    ob.attr("data-require-validate", "true");
                    __modal.on("hidden.bs.modal", function() {
                        if ($(this).find("input[name='toConsent']:checked").length > 0) {
                            $("#userOrgs input[name='organization']").each(function() {
                                $(this).removeAttr("data-require-validate");
                            });
                        }
                    });
                } else {
                    tnthAjax.setDefaultConsent(userId, parentOrg);
                }
            }
            var stateContainer = ob.closest(".state-container");
            if (stateContainer.length > 0) {
                var st = stateContainer.attr("state");
                if (st) {
                    $("#stateSelector").find("option[value='" + st + "']").prop("selected", true).val(st);
                    stateContainer.show();
                }
            }
        }
    }
};
OrgTool.prototype.getSelectedOrg = function() {
    return $("#userOrgs input[name='organization']:checked");
};
OrgTool.prototype.getConsentModal = function(parentOrg) {
    if (!parentOrg) {
        parentOrg = this.getElementParentOrg(this.getSelectedOrg());
    }
    if (parentOrg) {
        var __modal = $("#" + parentOrg + "_consentModal");
        if (__modal.length > 0) return __modal;
        else {
            var __defaultModal = this.getDefaultModal(this.getSelectedOrg() || $("#userOrgs input[name='organization'][value='" + parentOrg + "']"));
            if (__defaultModal && __defaultModal.length > 0) return __defaultModal;
            else return false;
        }
    } else return false;
};
OrgTool.prototype.handleEvent = function() {
    var self = this;
    $("#userOrgs input[name='organization']").each(function() {
        $(this).attr("data-save-container-id", "userOrgs");
        $(this).on("click", function() {
            var userId = self.getUserId();
            var parentOrg = self.getElementParentOrg(this);
            if ($(this).prop("checked")) {
                if ($(this).attr("id") !== "noOrgs") {
                    $("#noOrgs").prop("checked", false);
                } else {
                    $("#userOrgs input[name='organization']").each(function() {
                        if ($(this).attr("id") !== "noOrgs") {
                            $(this).prop("checked", false);
                        } else {
                            if (typeof sessionStorage != "undefined" && sessionStorage.getItem("noOrgModalViewed")) sessionStorage.removeItem("noOrgModalViewed");
                        }
                    });
                }
            } else {
                var isChecked = $("#userOrgs input[name='organization']:checked").length > 0;
                if (!isChecked) {
                    //do not attempt to update if all orgs are unchecked for staff/staff admin
                    var isStaff = false;
                    $("#rolesGroup input[name='user_type']").each(function() {
                        if (!isStaff && ($(this).is(":checked") && ($(this).val() == "staff" || $(this).val() == "staff_admin"))) {
                            $("#userOrgs .help-block").addClass("error-message").text(i18next.t("Cannot uncheck.  A staff member must be associated with an organization"));
                            isStaff = true;
                        }
                    });
                    if (!isStaff) $("#userOrgs .help-block").removeClass("error-message").text("");
                    else return false;
                    if (typeof sessionStorage != "undefined" && sessionStorage.getItem("noOrgModalViewed")) sessionStorage.removeItem("noOrgModalViewed");
                }
            }
            $("#userOrgs .help-block").removeClass("error-message").text("");

            if ($(this).attr("id") !== "noOrgs" && $("#fillOrgs").attr("patient_view")) {
                if (tnthAjax.hasConsent(userId, parentOrg)) {
                    assembleContent.demo(userId, true, $(this), true);
                } else {
                    var __modal = self.getConsentModal();
                    if (__modal.length > 0) __modal.modal("show");
                    else {
                        tnthAjax.setDefaultConsent(userId, parentOrg);
                        setTimeout(function() {
                            assembleContent.demo(userId, true, $(this), true);
                        }, 500);
                    }
                }
            } else {
                tnthAjax.handleConsent($(this));
                setTimeout(function() {
                    assembleContent.demo(userId, true, $(this), true);
                }, 500);
                tnthAjax.reloadConsentList(userId);
            }
            if ($("#locale").length > 0) {
                tnthAjax.getLocale(userId);
            }
        });
    });
};
OrgTool.prototype.getCommunicationArray = function() {
    var arrCommunication = [],self = this;
    $("#userOrgs input:checked").each(function() {
        if (parseInt($(this).val()) === 0) {
            return true; //don't count none
        }
        var oList = self.getOrgsList(), oi = oList[$(this).val()];
        if (!oi) {
            return true;
        }
        if (oi.language) {
            arrCommunication.push({
                "language": {"coding": [{"code": oi.language,"system": "urn:ietf:bcp:47"}]}
            });
        } else if (oi.extension && oi.extension.length > 0) {
            (oi.extension).forEach(function(ex) {
                if (String(ex.url) === String(SYSTEM_IDENTIFIER_ENUM.language) && ex.valueCodeableConcept.coding) {
                    arrCommunication.push({"language": { "coding": ex.valueCodeableConcept.coding}});
                }
            });
        }
    });
    if (arrCommunication.length === 0) {
        var defaultLocale = $("#sys_default_locale").val();
        if (defaultLocale) arrCommunication.push({
            "language": {
                "coding": [{
                    "code": defaultLocale,
                    "display": $("#locale").find("option[value='" + defaultLocale + "']").text(),
                    "system": "urn:ietf:bcp:47"
                }]
            }
        });

    }
    return arrCommunication;
};
OrgTool.prototype.getUserTopLevelParentOrgs = function(uo) {
    var parentList = [], self = this;
    if (uo) {
        uo.forEach(function(o) {
            var p = self.getTopLevelParentOrg(o);
            if (p && !self.inArray(p, parentList)) {
                parentList.push(p);
            }
        });
        return parentList;
    } else return false;
};
OrgTool.prototype.getTopLevelParentOrg = function(currentOrg) {
    if (!currentOrg) return false;
    var ml = this.getOrgsList(), self = this;
    if (ml && ml[currentOrg]) {
        if (ml[currentOrg].isTopLevel) {
            return currentOrg;
        } else {
            if (ml[currentOrg].parentOrgId) return self.getTopLevelParentOrg(ml[currentOrg].parentOrgId);
            else return currentOrg;
        }
    } else return false;
};
OrgTool.prototype.getChildOrgs = function(orgs, orgList) {
    if (!orgs || (orgs.length === 0)) {
        return orgList;
    } else {
        if (!orgList) orgList = [];
        var mainOrgsList = this.getOrgsList(), childOrgs = [];
        orgs.forEach(function(org) {
            var o = mainOrgsList[org.id];
            if (o) {
                orgList.push(org.id);
                var c = o.children ? o.children : null;
                if (c && c.length > 0) {
                    c.forEach(function(i) {
                        childOrgs.push(i);
                    });
                }
            }
        });
        return this.getChildOrgs(childOrgs, orgList);
    }
};
OrgTool.prototype.getHereBelowOrgs = function(userOrgs) {
    var mainOrgsList = this.getOrgsList(), self = this, here_below_orgs = [];
    if (!userOrgs) {
        var selectedOrg = this.getSelectedOrg();
        if (selectedOrg.length > 0) {
            userOrgs = [];
            selectedOrg.each(function() {
                userOrgs.push($(this).val());
            });
        }
    }
    if (userOrgs) {
        userOrgs.forEach(function(orgId) {
            here_below_orgs.push(orgId);
            var co = mainOrgsList[orgId], cOrgs = self.getChildOrgs((co && co.children ? co.children : null));
            if (cOrgs && cOrgs.length > 0) {
                here_below_orgs = here_below_orgs.concat(cOrgs);
            }
        });
    }
    return here_below_orgs;
};
OrgTool.prototype.morphPatientOrgs = function() {
    var checkedOrgs = {}, orgs = $("#userOrgs input[name='organization']");
    orgs.each(function() {
        $(this).closest("label").addClass("radio-label");
        if ($(this).prop("checked")) {
            checkedOrgs[$(this).val()] = true;
        }
        $(this).attr("type", "radio");
        if (checkedOrgs[$(this).val()]) {
            $(this).prop("checked", true);
        }
    });
};

var tnthAjax = {
    SNOMED_SYS_URL: "http://snomed.info/sct",
    CLINICAL_SYS_URL: "http://us.truenth.org/clinical-codes",
    CANCER_TREATMENT_CODE: "118877007",
    NONE_TREATMENT_CODE: "999",
    "beforeSend": function() {
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", $("#__CRSF_TOKEN").val());
                }
            }
        });
    },
    "getOrgTool": function(init) {
        if (!this.orgTool) {
            this.orgTool = new OrgTool();
            if (init) {
                this.orgTool.init();
            }
        }
        return this.orgTool;
    },
    "sendRequest": function(url, method, userId, params, callback) {
        if (!url) return false;
        if (!params) params = {};
        if (!params.attempts) params.attempts = 0;
        if (!params.max_attempts) params.max_attempts = 3;
        var self = this;
        var fieldHelper = this.FieldLoaderHelper, targetField = params.targetField || null;
        callback = callback || function() {};
        params.attempts++;
        fieldHelper.showLoader(targetField);
        $.ajax({
            type: method ? method : "GET",
            url: url,
            contentType: params.contentType ? params.contentType : "application/json; charset=utf-8",
            dataType: params.dataType ? params.dataType : "json",
            cache: (params.cache ? params.cache : false),
            async: (params.sync ? false : true),
            data: (params.data ? params.data : null),
            timeout: (params.timeout ? params.timeout : 5000) //set default timeout to 5 seconds
        }).done(function(data) {
            params.attempts = 0;
            if (data) {
                callback(data);
                fieldHelper.showUpdate(targetField);
            } else {
                callback({"error": true});
                fieldHelper.showError(targetField);
            }
        }).fail(function(xhr) {
            if (params.attempts < params.max_attempts) {
                (function(self, url, method, userId, params, callback) {
                    setTimeout(function() {
                        self.sendRequest(url, method, userId, params, callback);
                    }, 3000); //retry after 3 seconds
                })(self, url, method, userId, params, callback);
            } else {
                params.attempts = 0;
                if (callback) callback({"error": true});
                fieldHelper.showError(targetField);
                self.sendError(xhr, url, userId);
            }
        });
    },
    "sendError": function(xhr, url, userId) {
        if (xhr) {
            var errorMessage = "[Error occurred processing request]  status - " + (parseInt(xhr.status) == 0 ? "request timed out/network error" : xhr.status) + ", response text - " + (xhr.responseText ? xhr.responseText : "no response text returned from server");
            tnthAjax.reportError(userId ? userId : "Not available", url, errorMessage, true);
        }
    },
    "reportError": function(userId, page_url, message, sync) {
        //params need to contain the following: subject_id: User on which action is being attempted message: Details of the error event page_url: The page requested resulting in the error
        var params = {};
        params.subject_id = userId ? userId : 0;
        params.page_url = page_url ? page_url : window.location.href;
        params.message = "Error generated in JS - " + (message ? message : "no detail available"); //don't think we want to translate message sent back to the server here
        if (window.console) {
            console.log("Errors occurred.....");
            console.log(params);
        }
        $.ajax({
            type: "GET",
            url: "/report-error",
            contentType: "application/json; charset=utf-8",
            cache: false,
            async: (sync ? false : true),
            data: params
        }).done(function() {}).fail(function() {});
    },
    "FieldLoaderHelper": {
        delayDuration: 600,
        showLoader: function(targetField) {
            if (targetField && targetField.length > 0) {
                $("#" + targetField.attr("data-save-container-id") + "_load").css("opacity", 1);
            }
        },
        showUpdate: function(targetField) {
            var __timeout = this.delayDuration;
            if (targetField && targetField.length > 0) {
                setTimeout(function() {
                    (function(targetField) {
                        var containerId = targetField.attr("data-save-container-id");
                        var errorField = $("#" + containerId + "_error");
                        var successField = $("#" + containerId + "_success");
                        var loadingField = $("#" + containerId + "_load");
                        errorField.text("").css("opacity", 0);
                        successField.text(i18next.t("success"));
                        loadingField.animate({"opacity": 0}, __timeout, function() {
                            successField.animate({"opacity": 1}, __timeout, function() {
                                setTimeout(function() {
                                    successField.animate({"opacity": 0}, __timeout * 2);
                                }, __timeout * 2);
                            });
                        });
                    })(targetField);
                }, __timeout);
            }
        },
        showError: function(targetField) {
            targetField = targetField || $(targetField);
            var __timeout = this.delayDuration;
            if (targetField && targetField.length > 0) {
                setTimeout(function() {
                    (function(targetField) {
                        var containerId = targetField.attr("data-save-container-id");
                        var errorField = $("#" + containerId + "_error");
                        var successField = $("#" + containerId + "_success");
                        var loadingField = $("#" + containerId + "_load");
                        errorField.text(i18next.t("Unable to update. System/Server Error."));
                        successField.text("").css("opacity", 0);
                        loadingField.animate({"opacity": 0}, __timeout, function() {
                            errorField.animate({"opacity": 1}, __timeout, function() {
                                setTimeout(function() {
                                    errorField.animate({"opacity": 0}, __timeout * 2);
                                }, __timeout * 2);
                            });
                        });
                    })(targetField);
                }, __timeout);
            }
        }
    },
    "getStillNeededCoreData": function(userId, sync, callback, entry_method) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User Id is required")});
            return false;
        }
        var __url = "/api/coredata/user/" + userId + "/still_needed" + (entry_method ? "?entry_method=" + (entry_method).replace(/\_/g, " ") : "");
        this.sendRequest(__url, "GET", userId, {sync: sync,cache: true}, function(data) {
            if (data) {
                if (!data.error) { /* example data format:[{"field": "name"}, {"field": "website_terms_of_use", "collection_method": "ACCEPT_ON_NEXT"}]*/
                    var ACCEPT_ON_NEXT = "ACCEPT_ON_NEXT";
                    var fields = (data.still_needed).map(function(item) {
                        return item.field;
                    });
                    if ($("#topTerms").length > 0) {
                        var acceptOnNextCheckboxes = [];
                        (data.still_needed).forEach(function(item) {
                            var matchedTermsCheckbox = $("#termsCheckbox [data-type='terms'][data-core-data-type='" + $.trim(item.field) + "']");
                            if (matchedTermsCheckbox.length > 0) {
                                matchedTermsCheckbox.attr({
                                    "data-required": "true",
                                    "data-collection-method": item.collection_method
                                });
                                var parentNode = matchedTermsCheckbox.closest("label.terms-label");
                                if (parentNode.length > 0) {
                                    parentNode.show().removeClass("tnth-hide");
                                    if (String(item.collection_method).toUpperCase() === ACCEPT_ON_NEXT) {
                                        parentNode.find("i").removeClass("fa-square-o").addClass("fa-check-square-o").addClass("edit-view");
                                        $("#termsCheckbox").addClass("tnth-hide");
                                        $("#termsText").addClass("agreed");
                                        $("#termsCheckbox_default").removeClass("tnth-hide");
                                        $("#topTerms .terms-of-use-intro").addClass("tnth-hide");
                                        $("#aboutForm .reg-complete-container").addClass("inactive"); //hiding thank you and continue button for accept on next collection method
                                        acceptOnNextCheckboxes.push(parentNode);
                                    }
                                }
                            }
                        });
                        if (acceptOnNextCheckboxes.length > 0) { //require for accept on next collection method
                            $("#next").on("click", function() {
                                acceptOnNextCheckboxes.forEach(function(ckBox) {
                                    ckBox.trigger("click");
                                });
                            });
                        }
                    }
                    if (fields.indexOf("localized") === -1) {
                        $("#patMeta").remove();
                    }
                    callback(fields);
                } else {
                    callback({"error": i18next.t("unable to get needed core data")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});

            }
        });
    },
    "getRequiredCoreData": function(userId, sync, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User Id is required")});
            return false;
        }
        this.sendRequest("/api/coredata/user/" + userId + "/required", "GET", userId, {sync: sync,cache: true}, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.required) {
                        callback(data.required);
                    } else {
                        callback({"error": i18next.t("no data returned")});
                    }
                } else {
                    callback({"error": i18next.t("unable to get required core data")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "getOptionalCoreData": function(userId, sync, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User Id is required")});
            return false;
        }
        var __url = "/api/coredata/user/" + userId + "/optional", sessionStorageKey = "optionalCoreData_" + userId;
        if (sessionStorage.getItem(sessionStorageKey)) {
            callback(JSON.parse(sessionStorage.getItem(sessionStorageKey)));
        } else {
            this.sendRequest(__url, "GET", userId, {sync: sync,cache: true}, function(data) {
                if (data) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("no data found")});
                }
            });
        }
    },
    "getPortalFooter": function(userId, sync, containerId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback("<div class='error-message'>" + i18next.t("User Id is required") + "</div>");
            return false;
        }
        this.sendRequest("/api/portal-footer-html/", "GET", userId, {sync: sync,cache: true,"dataType": "html"}, function(data) {
            if (data) {
                if (!data.error) {
                    if (containerId) $("#" + containerId).html(data);
                    callback(data);
                } else {
                    callback("<div class='error-message'>" + i18next.t("Unable to retrieve portal footer html") + "</div>");
                }
            } else {
                callback("<div class='error-message'>" + i18next.t("No data found") + "</div>");
            }
        });
    },
    "getOrgs": function(userId, sync, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/organization", "GET", userId, {sync: sync,cache: true}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".get-orgs-error").html("");
                    callback(data);
                } else {
                    var errorMessage = i18next.t("Server error occurred retrieving organization/clinic information.");
                    $(".get-orgs-error").html(errorMessage);
                    callback({"error": errorMessage});
                }
            }
        });
    },
    "consentParams": {"staff_editable": true,"include_in_reports": true,"send_reminders": true},
    "getConsent": function(userId, sync, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/consent", "GET", userId, {sync: sync}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".get-consent-error").html("");
                    callback(data);
                    return true;
                } else {
                    var errorMessage = i18next.t("Server error occurred retrieving consent information.");
                    callback({"error": errorMessage});
                    $(".get-consent-error").html(errorMessage);
                    return false;
                }
            }
        });
    },
    "setConsent": function(userId, params, status, sync, callback) {
        if (userId && params) {
            var consented = this.hasConsent(userId, params.org, status);
            var __url = "/api/user/" + userId + "/consent";
            if (!consented || params.testPatient) {
                var data = {};
                data.user_id = userId;
                data.organization_id = params.org;
                data.agreement_url = params.agreementUrl;
                data.staff_editable = (String(params.staff_editable) !== "null"  && String(params.staff_editable) !== "undefined" ? params.staff_editable : false);
                data.include_in_reports = (String(params.include_in_reports) !== "null" && String(params.include_in_reports) !== "undefined" ? params.include_in_reports : false);
                data.send_reminders = (String(params.send_reminders) !== "null" &&  String(params.send_reminders) !== "undefined"? params.send_reminders : false);
                if (params.acceptance_date) {
                    data.acceptance_date = params.acceptance_date;
                }

                this.sendRequest(__url, "POST", userId, {sync: sync, data: JSON.stringify(data)}, function(data) {
                    if (data) {
                        if (!data.error) {
                            $(".set-consent-error").html("");
                            if (callback) callback(data);
                        } else {
                            var errorMessage = i18next.t("Server error occurred setting consent status.");
                            if (callback) callback({"error": errorMessage});
                            $(".set-consent-error").html(errorMessage);
                        }
                    }
                });
            }
        }
    },
    "setDefaultConsent": function(userId, orgId) {
        if (!userId) return false;
        var stockConsentUrl = $("#stock_consent_url").val(), agreementUrl = "";
        if (stockConsentUrl) {
            var orgElement = $("#" + orgId + "_org");
            var orgName = orgElement.attr("data-parent-name");
            if (!orgName) {
                orgElement.attr("data-org-name");
            }
            agreementUrl = stockConsentUrl.replace("placeholder", encodeURIComponent(orgName));
        }
        if (agreementUrl) {
            var params = this.consentParams;
            params.org = orgId;
            params.agreementUrl = agreementUrl;
            this.setConsent(userId, params, "default");
            setTimeout(function() { //need to remove all other consents associated w un-selected org(s)
                tnthAjax.removeObsoleteConsent();
            }, 100);
            tnthAjax.reloadConsentList(userId);
            $($("#consentContainer .error-message").get(0)).text("");
        } else {
            $($("#consentContainer .error-message").get(0)).text(i18next.t("Unable to set default consent agreement"));
        }
    },
    deleteConsent: function(userId, params) {
        if (userId && params) {
            var consented = this.getAllValidConsent(userId, params.org);
            if (consented) {
                var self = this, __url = "/api/user/" + userId + "/consent";
                consented.forEach(function(orgId) { //delete all consents for the org
                    if (params.exclude) {
                        var arr = params.exclude.split(",");
                        var found = false;
                        arr.forEach(function(o) {
                            if (!found) {
                                if (o == orgId) found = true;
                            }
                        });
                        if (found) return true;
                    }
                    self.sendRequest(__url, "DELETE", userId, {sync: true,data: JSON.stringify({"organization_id": parseInt(orgId)})}, function(data) {
                        if (data) {
                            if (!data.error) {
                                $(".delete-consent-error").html("");
                            } else {
                                $(".delete-consent-error").html(i18next.t("Server error occurred removing consent."));
                            }
                        }
                    });
                });
            }
        }
    },
    withdrawConsent: function(userId, orgId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
            return false;
        }
        if (!orgId) {
            callback({"error": i18next.t("Organization id is required.")});
            return false;
        }
        params = params || {};
        this.sendRequest("/api/user/" + userId + "/consent/withdraw",
            "POST",
            userId, {sync: (params.sync ? true : false),data: JSON.stringify({organization_id: orgId})},
            function(data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred setting consent status.")});
                }
            }
        );
    },
    getAllValidConsent: function(userId, orgId) {
        if (!userId) return false;
        if (!orgId) return false;
        var consentedOrgIds = [];
        this.sendRequest("/api/user/" + userId + "/consent", "GET", userId, {sync: true}, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.consent_agreements) {
                        var d = data.consent_agreements;
                        if (d.length > 0) {
                            d.forEach(function(item) {
                                var expired = item.expires ? tnthDates.getDateDiff(String(item.expires)) : 0;
                                if (!item.deleted && !(expired > 0)) {
                                    if (orgId == "all") consentedOrgIds.push(item.organization_id);
                                    else if (orgId == item.organization_id) consentedOrgIds.push(orgId);
                                }
                            });
                        }
                    }
                } else {
                    return false;
                }
            }
            return consentedOrgIds;
        });
        return consentedOrgIds;
    },
    hasConsent: function(userId, orgId, filterStatus) {  /****** NOTE - this will return the latest updated consent entry *******/
        if (!userId) return false;
        if (!orgId) return false;
        if (String(filterStatus) === "default") {
            return false;
        }
        var consentedOrgIds = [], expired = 0, found = false, suspended = false, item = null;
        var __url = "/api/user/" + userId + "/consent";
        var self = this;
        self.sendRequest(__url, "GET", userId, {sync: true}, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.consent_agreements) {
                        var d = data.consent_agreements;
                        if (d.length > 0) {
                            d = d.sort(function(a, b) {
                                return new Date(b.signed) - new Date(a.signed); //latest comes first
                            });
                            item = d[0];
                            expired = item.expires ? tnthDates.getDateDiff(String(item.expires)) : 0;
                            if (item.deleted) found = true;
                            if (expired > 0) found = true;
                            if (item.staff_editable && item.include_in_reports && !item.send_reminders) suspended = true;
                            if (!found) {
                                if (orgId == item.organization_id) {
                                    switch (filterStatus) {
                                    case "suspended":
                                        if (suspended) found = true;
                                        break;
                                    case "purged":
                                        found = true;
                                        break;
                                    case "consented":
                                        if (!suspended) {
                                            if (item.staff_editable && item.send_reminders && item.include_in_reports) found = true;
                                        }
                                        break;
                                    default:
                                        found = true; //default is to return both suspended and consented entries
                                    }
                                    if (found) consentedOrgIds.push(orgId);

                                }
                            }
                        }
                    }

                } else {
                    return false;
                }
            }
        });
        return consentedOrgIds.length > 0 ? consentedOrgIds : null;
    },
    removeObsoleteConsent: function() {
        var userId = $("#fillOrgs").attr("userId"), co = [], OT = this.getOrgTool();
        $("#userOrgs input[name='organization']").each(function() {
            if ($(this).is(":checked")) {
                var po = OT.getElementParentOrg(this);
                co.push($(this).val());
                if (po) co.push(po);
            }
        });
        tnthAjax.deleteConsent(userId, {org: "all", exclude: co.join(",")}); //exclude currently selected orgs
    },
    handleConsent: function(obj) {
        var self = this, OT = this.getOrgTool(), userId = $("#fillOrgs").attr("userId") || $("#userOrgs").attr("userId");
        var configVar = $("#profile_CONSENT_WITH_TOP_LEVEL_ORG").val();
        if (!configVar) {
            tnthAjax.getConfigurationByKey("CONSENT_WITH_TOP_LEVEL_ORG", userId, {sync: true}, false, true);
        }
        $(obj).each(function() {
            var parentOrg = OT.getElementParentOrg(this);
            var orgId = $(this).val();
            var cto = String(configVar).toLowerCase() === "true";
            if ($(this).prop("checked")) {
                if ($(this).attr("id") !== "noOrgs") {
                    if (parentOrg) {
                        var agreementUrl = $("#" + parentOrg + "_agreement_url").val();
                        if (agreementUrl && agreementUrl != "") {
                            var params = self.consentParams;
                            params.org = cto ? parentOrg : orgId;
                            params.agreementUrl = agreementUrl;
                            setTimeout(function() {
                                tnthAjax.setConsent($("#fillOrgs").attr("userId"), params, "all", true, function() {
                                    tnthAjax.removeObsoleteConsent();
                                });
                            }, 350);
                        } else {
                            if (cto) {
                                tnthAjax.setDefaultConsent(userId, parentOrg);
                            }
                        }
                    }
                } else {
                    if (cto) {
                        var topLevelOrgs = OT.getTopLevelOrgs();
                        topLevelOrgs.forEach(function(i) {
                            (function(orgId) {
                                setTimeout(function() {
                                    tnthAjax.deleteConsent($("#fillOrgs").attr("userId"), {
                                        "org": orgId
                                    });
                                }, 350);
                            })(i);
                        });
                    } else {
                        $("#userOrgs").find("input[name='organization']").each(function() { //delete all orgs
                            (function(orgId) {
                                setTimeout(function() {
                                    tnthAjax.deleteConsent($("#fillOrgs").attr("userId"), {
                                        "org": orgId
                                    });
                                }, 350);
                            })($(this).val());
                        });
                    }
                }
            } else {
                //delete only when all the child orgs from the parent org are unchecked as consent agreement is with the parent org
                if (cto) {
                    var childOrgs = [];
                    if ($("#fillOrgs").attr("patient_view")) childOrgs = $("#userOrgs div.org-container[data-parent-id='" + parentOrg + "']").find("input[name='organization']");
                    else childOrgs = $("#userOrgs input[data-parent-id='" + parentOrg + "']");
                    var allUnchecked = true;
                    childOrgs.each(function() {
                        if ($(this).prop("checked")) allUnchecked = false;
                    });
                    if (allUnchecked && childOrgs.length > 0) {
                        (function(orgId) {
                            setTimeout(function() {
                                tnthAjax.deleteConsent($("#fillOrgs").attr("userId"), {
                                    "org": orgId
                                });
                            }, 350);
                        })(parentOrg);
                    }
                } else {
                    (function(orgId) {
                        setTimeout(function() {
                            tnthAjax.deleteConsent($("#fillOrgs").attr("userId"), {"org": orgId});
                        }, 350);
                    })(orgId);
                }
            }
        });
    },
    /**** this function is used when this section becomes editable, note: this is called after the user has edited the consent list; this will refresh the list ****/
    "reloadConsentList": function(userId) {
        if (typeof ProfileObj !== "undefined") ProfileObj.reloadConsentList(userId);
    },
    "getDemo": function(userId, noOverride, sync, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/demographics/" + userId, "GET", userId, {sync: sync}, function(data) {
            if (!data.error) {
                $(".get-demo-error").html("");
                callback(data);
            } else {
                var errorMessage = i18next.t("Server error occurred retrieving demographics information.");
                $(".get-demo-error").html(errorMessage);
                callback({"error": errorMessage});
            }
        });
    },
    "putDemo": function(userId, toSend, targetField, sync) {
        this.sendRequest("/api/demographics/" + userId, "PUT", userId, {sync: sync, data: JSON.stringify(toSend),targetField: targetField}, function(data) {
            if (!data.error) {
                $(".put-demo-error").html("");
            } else {
                var errorMessage = i18next.t("Server error occurred setting demographics information.");
                if ($(".put-demo-error").length == 0) $(".default-error-message-container").append("<div class='put-demo-error error-message'>" + errorMessage + "</div>");
                else $(".put-demo-error").html(errorMessage);
            }
        });
    },
    "getLocale": function(userId) {
        this.sendRequest("/api/demographics/" + userId, "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.communication) {
                        $("#profileLocaleTimezoneContainer .get-locale-error").html("");
                    }
                } else {
                    $("#profileLocaleTimezoneContainer .get-locale-error").html(i18next.t("Server error occurred retrieving locale information."));
                }
            }
        });
    },
    "hasTreatment": function(data) {
        var found = false, self = this;
        if (data && data.entry && data.entry.length > 0) {
            data.entry = data.entry.sort(function(a, b) { // sort from newest to oldest based on lsat updated date
                return new Date(b.resource.meta.lastUpdated) - new Date(a.resource.meta.lastUpdated);
            });
            (data.entry).forEach(function(item) {
                if (!found) {
                    var resourceItemCode = item.resource.code.coding[0].code;
                    var system = item.resource.code.coding[0].system;
                    var procId = item.resource.id;
                    if ((resourceItemCode == self.CANCER_TREATMENT_CODE && (system == self.SNOMED_SYS_URL)) || (resourceItemCode == self.NONE_TREATMENT_CODE && (system == self.CLINICAL_SYS_URL))) {
                        found = {"code": resourceItemCode,"id": procId};
                    }
                }
            });
        }
        return found;
    },
    "getTreatment": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required")});
            return false;
        }
        this.sendRequest("/api/patient/" + userId + "/procedure", "GET", userId, null, function(data) {
            if (data.error) {
                $("#userProcedures").html("<span class='error-message'>" + i18next.t("Error retrieving data from server") + "</span>");
            }
            callback(data);
        });
    },
    "postTreatment": function(userId, started, treatmentDate, targetField) {
        if (!userId) return false;
        tnthAjax.deleteTreatment(userId, targetField);
        var code = this.NONE_TREATMENT_CODE, display = "None", system = this.CLINICAL_SYS_URL;
        if (started) {
            code = this.CANCER_TREATMENT_CODE;
            display = "Procedure on prostate";
            system = this.SNOMED_SYS_URL;
        }
        if (!treatmentDate) {
            var date = new Date();
            treatmentDate = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate();  //in yyyy-mm-dd format
        }
        var procID = [{"code": code,"display": display,"system": system}];
        var procArray = {};
        procArray.resourceType = "Procedure";
        procArray.subject = {"reference": "Patient/" + userId};
        procArray.code = {"coding": procID};
        procArray.performedDateTime = treatmentDate ? treatmentDate : "";

        tnthAjax.postProc(userId, procArray, targetField);
    },
    deleteTreatment: function(userId, targetField) {
        var self = this;
        this.sendRequest("/api/patient/" + userId + "/procedure", "GET", userId, {sync: true}, function(data) {
            if (data) {
                if (!data.error) {
                    var treatmentData = tnthAjax.hasTreatment(data);
                    if (treatmentData) {
                        if (treatmentData.code == self.CANCER_TREATMENT_CODE) {
                            tnthAjax.deleteProc(treatmentData.id, targetField, true);
                        } else {
                            tnthAjax.deleteProc(treatmentData.id, targetField, true);
                        }
                    }

                } else {
                    return false;
                }
            } else return false;
        });
    },
    "getProc": function(userId, newEntry, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/patient/" + userId + "/procedure", "GET", userId, null, function(data) {
            callback(data);
        });
    },
    "postProc": function(userId, toSend, targetField, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/procedure", "POST", userId, {data: JSON.stringify(toSend),targetField: targetField}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".get-procs-error").html("");
                    callback(data);
                } else {
                    var errorMessage = i18next.t("Server error occurred saving procedure/treatment information.");
                    $("#userProcuedures .get-procs-error").html(errorMessage);
                    callback({error: errorMessage});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "deleteProc": function(procedureId, targetField, sync) {
        this.sendRequest("/api/procedure/" + procedureId, "DELETE", null, {sync: sync,targetField: targetField}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".del-procs-error").html("");
                } else {
                    $(".del-procs-error").html(i18next.t("Server error occurred removing procedure/treatment information."));
                }
            }
        });
    },
    "hasRole": function(userId, roleName, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User ID is required.")});
            return false;
        }
        if (!roleName) {
            callback({"error": i18next.t("Role must be provided")});
            return false;
        }
        tnthAjax.getRoles(userId, false, function(data) {
            if (data.roles) {
                var matchedRole = $.grep(data.roles, function(role) {
                    return String(role.name).toLowerCase() === String(roleName).toLowerCase();
                });
                callback({"matched": matchedRole.length > 0});
            } else {
                callback({"error": i18next.t("no roles found for user")});
            }
        }, {"sync": true});
    },
    "getRoleList": function(callback) {
        this.sendRequest("/api/roles", "GET", null, null, function(data) {
            callback = callback || function() {};
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    var errorMessage = i18next.t("Server error occurred retrieving roles information.");
                    $(".get-roles-error").html(errorMessage);
                    callback({"error": errorMessage});
                }
            } else {
                callback({"error": "No roles list found"});
            }
        });
    },
    "getRoles": function(userId, isProfile, callback, params) {
        callback = callback || function() {};
        var sessionStorageKey = "userRole_" + userId;
        if (sessionStorage.getItem(sessionStorageKey)) {
            var data = JSON.parse(sessionStorage.getItem(sessionStorageKey));
            callback(data);
        } else {
            this.sendRequest("/api/user/" + userId + "/roles", "GET", userId, params, function(data) {
                if (data) {
                    if (!data.error) {
                        $(".get-roles-error").html("");
                        sessionStorage.setItem(sessionStorageKey, JSON.stringify(data));
                        callback(data);
                    } else {
                        var errorMessage = i18next.t("Server error occurred retrieving user role information.");
                        $(".get-roles-error").html(errorMessage);
                        callback({"error": errorMessage});
                    }
                }
            });
        }
    },
    "putRoles": function(userId, toSend, targetField) {
        this.sendRequest("/api/user/" + userId + "/roles", "PUT", userId, {data: JSON.stringify(toSend),targetField: targetField}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".put-roles-error").html("");
                    if (sessionStorage.getItem("userRole_" + userId)) {
                        sessionStorage.setItem("userRole_" + userId, "");
                    }
                } else {
                    $(".put-roles-error").html(i18next.t("Server error occurred setting user role information."));
                }
            }
        });
    },
    "deleteRoles": function(userId, toSend) {
        this.sendRequest("/api/user/" + userId, "GET", userId, {data: JSON.stringify(toSend)}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".delete-roles-error").html("");
                } else {
                    $(".delete-roles-error").html(i18next.t("Server error occurred deleting user role."));
                }
            }
        });
    },
    "getClinical": function(userId, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/patient/" + userId + "/clinical", "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    $(".get-clinical-error").html("");
                    callback(data);
                } else {
                    var errorMessage = i18next.t("Server error occurred retrieving clinical data.");
                    $(".get-clinical-error").html(errorMessage);
                    callback({"error": errorMessage});
                }
            }
        });
    },
    "putClinical": function(userId, toCall, toSend, targetField) {
        this.sendRequest("/api/patient/" + userId + "/clinical/" + toCall, "POST", userId, {data: JSON.stringify({value: toSend}),targetField: targetField}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".put-clinical-error").html("");
                } else {
                    $(".put-clinical-error").html(i18next.t("Server error occurred updating clinical data."));
                }
            }
        });
    },
    "getObservationId": function(userId, code) {
        if (!userId) return false;
        var obId = "",_code = "";
        this.sendRequest("/api/patient/" + userId + "/clinical", "GET", userId, {sync: true}, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.entry) {
                        (data.entry).forEach(function(item) {
                            if (!obId) {
                                _code = item.content.code.coding[0].code;
                                if (_code == code) obId = item.content.id;
                            }
                        });
                    }
                }
            }
        });
        return obId;
    },
    "postClinical": function(userId, toCall, toSend, status, targetField, params) {
        if (!userId) return false;
        if (!params) params = {};
        var code = "", display = "";
        switch (toCall) {
        case "biopsy":
            code = "111";
            display = "biopsy";
            break;
        case "pca_diag":
            code = "121";
            display = "PCa diagnosis";
            break;
        case "pca_localized":
            code = "141";
            display = "PCa localized diagnosis";
        }
        if (!code) return false;
        var system = this.CLINICAL_SYS_URL;
        var method = "POST";
        var url = "/api/patient/" + userId + "/clinical";
        var obsCode = [{"code": code,"display": display,"system": system}];
        var obsArray = {};
        obsArray.resourceType = "Observation";
        obsArray.code = {
            "coding": obsCode
        };
        obsArray.issued = params.issuedDate ? params.issuedDate : "";
        obsArray.status = status ? status : "";
        obsArray.valueQuantity = {"units": "boolean","value": toSend};
        if (params.performer) obsArray.performer = params.performer;
        var obsId = tnthAjax.getObservationId(userId, code);
        if (obsId) {
            method = "PUT";
            url = url + "/" + obsId;
        }
        this.sendRequest(url, method, userId, {data: JSON.stringify(obsArray),targetField: targetField}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".post-clinical-error").html("");
                } else {
                    $(".post-clinical-error").html(i18next.t("Server error occurred updating clinical data."));
                }
            }
        });
    },
    "getTermsUrl": function(sync, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/tou", "GET", null, {sync: sync}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".get-tou-error").html("");
                    if (data.url) {
                        $("#termsURL").attr("data-url", data.url);
                        $("#termsCheckbox_default .terms-url").attr("href", data.url);
                        callback({"url": data.url});
                    } else {
                        callback({"error": i18next.t("no url returned")});
                    }
                } else {
                    $(".get-tou-error").html(i18next.t("Server error occurred retrieving tou url."));
                    callback({"error": i18next.t("Server error")});
                }
            }
        });
    },
    "getInstrumentsList": function(sync, callback) { //return instruments list by organization(s)
        callback = callback || function() {};
        this.sendRequest("api/questionnaire_bank", "GET", null, {
            sync: sync
        }, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.entry) {
                        if ((data.entry).length === 0) {
                            callback({"error": i18next.t("no data returned")});
                        } else {
                            var qList = {};
                            (data.entry).forEach(function(item) {
                                if (item.organization) {
                                    var orgID = (item.organization.reference).split("/")[2];
                                    if (!qList[orgID]) qList[orgID] = []; //don't assign orgID to object if it was already present
                                    if (item.questionnaires) {
                                        (item.questionnaires).forEach(function(q) {
                                            /*
                                             * add instrument name to instruments array for the org - will not add if it is already in the array
                                             * NOTE: inArray returns -1 if the item is NOT in the array
                                             */
                                            if ($.inArray(q.questionnaire.display, qList[orgID]) == -1) {
                                                qList[orgID].push(q.questionnaire.display);
                                            }
                                        });
                                    }
                                }
                            });
                            callback(qList);
                        }
                    } else {
                        callback({"error": i18next.t("no data returned")});
                    }
                } else {
                    callback({"error": i18next.t("error retrieving instruments list")});
                }
            }
        });
    },
    "getTerms": function(userId, type, sync, callback, params) {
        callback = callback || function() {};
        if (!params) params = {};
        var url = "/api/user/{userId}/tou{type}{all}".replace("{userId}", userId)
            .replace("{type}", type ? ("/" + type) : "")
            .replace("{all}", (params.hasOwnProperty("all") ? "?all=true" : ""));
        this.sendRequest(url, "GET", userId, {sync: sync}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".get-tou-error").html("");
                    callback(data);
                } else {
                    var errorMessage = i18next.t("Server error occurred retrieving tou data.");
                    $(".get-tou-error").html(errorMessage);
                    callback({"error": errorMessage});
                }
            }
        });
    },
    "postTermsByUser": function(userId, toSend) {
        this.sendRequest("/api/user/" + userId + "/tou/accepted", "POST", userId, {
            data: JSON.stringify(toSend)
        }, function(data) {
            if (data) {
                if (!data.error) {
                    $(".post-tou-error").html("");
                } else {
                    $(".post-tou-error").html(i18next.t("Server error occurred saving terms of use information."));
                }
            }
        });
    },
    "postTerms": function(toSend) {
        this.sendRequest("/api/tou/accepted", "POST", null, {data: JSON.stringify(toSend)}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".post-tou-error").html("");
                } else {
                    $(".post-tou-error").html(i18next.t("Server error occurred saving terms of use information."));
                }
            }
        });
    },
    "accessUrl": function(userId, sync, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
        }
        this.sendRequest("/api/user/" + userId + "/access_url", "GET", userId, {sync: sync}, function(data) {
            if (data) {
                if (!data.error) {
                    callback({url: data.access_url});
                } else {
                    callback({"error": i18next.t("Error occurred retrieving access url.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "invite": function(userId, data, callback) {
        callback = callback || function() {};
        if (!data) {
            callback({"error": i18next.t("Invite data are required.")});
        }
        this.sendRequest("/invite", "POST", userId, {
            "contentType": "application/x-www-form-urlencoded; charset=UTF-8",
            "data": data,
            "dataType": "html"
        }, function(data) {
            if (data) {
                callback(data);
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "passwordReset": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
        }
        this.sendRequest("/api/user/" + userId + "/password_reset", "POST", userId, {"contentType": "application/x-www-form-urlencoded; charset=UTF-8"}, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred sending password reset request.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "assessmentStatus": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
        }
        this.sendRequest("/api/patient/" + userId + "/assessment-status", "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving assessment status.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "updateAssessment": function(userId, data, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
        }
        if (!data) {
            callback({"error": i18next.t("Questionnaire response data is required.")});
        }
        this.sendRequest("/api/patient/" + userId + "/assessment", "PUT", userId, {data: JSON.stringify(data)}, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving assessment list.")});
                }

            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "assessmentList": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/patient/" + userId + "/assessment", "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving assessment list.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "assessmentReport": function(userId, instrumentId, callback) {
        callback = callback || function() {};
        if (!userId || !instrumentId) {
            callback({error: i18next.t("User id and instrument Id are required.")});
            return false;
        }
        this.sendRequest("/api/patient/" + userId + "/assessment/" + instrumentId, "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving assessment report.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "getCurrentQB": function(userId, completionDate, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        params = params || {};
        this.sendRequest("/api/user/" + userId + "/questionnaire_bank", "GET", userId, {data: {as_of_date: completionDate}, sync: params.sync ? true : false}, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving current questionnaire bank for user.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "patientReport": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/user_documents?document_type=PatientReport", "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving patient report.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "setTablePreference": function(userId, tableName, params, callback) {
        callback = callback || function() {};
        if (!userId || !tableName) {
            callback({error: "User Id and table name is required for setting preference."});
            return false;
        }
        if (!params) params = {};
        this.sendRequest("/api/user/" + userId + "/table_preferences/" + tableName, "PUT", userId, {"data": params.data,"sync": params.sync}, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred setting table preference.")});
                }
            }
        });
    },
    "getTablePreference": function(userId, tableName, params, callback) {
        callback = callback || function() {};
        if (!userId || !tableName) {
            callback({error: "User Id and table name is required for setting preference."});
            return false;
        }
        if (!params) params = {};
        this.sendRequest("/api/user/" + userId + "/table_preferences/" + tableName, "GET", userId, {"sync": params.sync}, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred setting table preference.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "initNotifications": function(callback) {
        this.getNotification($("#notificationUserId").val(), false, function(data) {
            if (callback) callback(data);
        });
    },
    "getNotification": function(userId, params, callback) {
        callback = callback || function() {};
        if (userId) {
            if (!params) params = {};
            var notificationSessionKey = "notification_" + userId;
            if (sessionStorage.getItem(notificationSessionKey)) {
                callback(JSON.parse(sessionStorage.getItem(notificationSessionKey)));
            } else {
                this.sendRequest("/api/user/" + userId + "/notification", "GET", userId, {
                    "sync": params.sync
                }, function(data) {
                    if (data) {
                        if (!data.error) {
                            callback(data);
                            sessionStorage.setItem(notificationSessionKey, JSON.stringify(data));
                        } else {
                            callback({"error": i18next.t("Error occurred retrieving notification.")});
                        }
                    } else {
                        callback({"error": i18next.t("no data returned")});
                    }
                });
            }
        } else {
            callback({"error": i18next.t("User id is required")});
        }
    },
    "deleteNotification": function(userId, notificationId, params, callback) {
        if (!callback) {
            callback = function(data) {
                return data;
            };
        }
        if (!userId) {
            callback({"error": i18next.t("User Id is required")});
            return false;
        }
        if (parseInt(notificationId) < 0 || !notificationId) {
            callback({"error": i18next.t("Notification id is required.")});
        }
        if (!params) params = {};
        var self = this;
        this.getNotification(userId, false, function(data) {
            if (data.notifications) {
                /*
                 * check if there is notification for this id -dealing with use case where user deletes same notification in a separate open window
                 */
                var arrNotification = $.grep(data.notifications, function(notification) {
                    return notification.id == notificationId;
                });
                if (arrNotification.length > 0) { //delete notification only if it exists
                    self.sendRequest("/api/user/" + userId + "/notification/" + notificationId, "DELETE", userId, {
                        "sync": params.sync
                    }, function(data) {
                        if (data) {
                            if (!data.error) {
                                callback(data);
                            } else {
                                callback({"error": i18next.t("Error occurred deleting notification.")});
                            }
                        } else {
                            callback({"error": i18next.t("no data returned")});
                        }
                    });
                }
            }
        });
    },
    "emailLog": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/messages", "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving email audit entries.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "auditLog": function(userId, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/audit", "GET", userId, null, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving audit log.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "setting": function(key, userId, params, callback) {
        callback = callback || function() {};
        if (!key) {
            callback({"error": i18next.t("configuration key is required.")});
            return false;
        }
        if (!params) params = {};
        this.sendRequest("/api/settings/" + key, "GET", userId, {
            "sync": params.sync
        }, function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred retrieving content for configuration key.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });
    },
    "deleteUser": function(userId, params, callback) {
        callback = callback||function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required")});
            return false;
        }
        this.sendRequest("/api/user/" + userId, "DELETE", userId, (params || {}), function(data) {
            if (data) {
                if (!data.error) {
                    callback(data);
                } else {
                    callback({"error": i18next.t("Error occurred deleting user.")});
                }
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        });

    },
    "treatmentOptions": function(userId, params, callback) {
        this.sendRequest("/patients/treatment-options", "GET", userId, (params || {}), function(data) {
            if (data) {
                if (!data.error) {
                    if (callback) callback(data);
                } else {
                    if (callback) callback({
                        "error": i18next.t("Error occurred retrieving treatment options.")
                    });
                }
            } else {
                if (callback) callback({
                    "error": i18next.t("no data returned")
                });
            }
        });
    },
    "setConfigurationUI": function(configKey, value) {
        if (configKey) {
            if ($("#profile_" + configKey).length === 0) {
                $("body").append("<input type='hidden' id='profile_" + configKey + "' value='" + (value ? value : "") + "'/>");
            }
        }
    },
    "getConfigurationByKey": function(configVar, userId, params, callback, setConfigInUI) {
        callback = callback || function() {};
        var self = this;
        if (!userId) {
            callback({
                "error": i18next.t("User id is required.")
            });
            return false;
        }
        if (!configVar) {
            callback({
                "error": i18next.t("configuration variable name is required.")
            });
            return false;
        }
        var sessionConfigKey = "config_" + configVar + "_" + userId;
        if (sessionStorage.getItem(sessionConfigKey)) {
            var data = JSON.parse(sessionStorage.getItem(sessionConfigKey));
            if (setConfigInUI) {
                self.setConfigurationUI(configVar, data[configVar] + "");
            }
            callback(data);
        } else {
            this.sendRequest("/api/settings/" + configVar, "GET", userId, (params || {}), function(data) {
                if (data) {
                    callback(data);
                    if (data.hasOwnProperty(configVar)) {
                        if (setConfigInUI) {
                            self.setConfigurationUI(configVar, data[configVar] + "");
                        }
                        sessionStorage.setItem(sessionConfigKey, JSON.stringify(data));
                    }
                } else {
                    callback({
                        "error": i18next.t("no data returned")
                    });
                }
            });
        }
    },
    "getConfiguration": function(userId, params, callback) {
        callback = callback || function() {};
        var sessionConfigKey = "settings_" + userId;
        if (sessionStorage.getItem(sessionConfigKey)) {
            var data = JSON.parse(sessionStorage.getItem(sessionConfigKey));
            callback(data);
        } else {
            this.sendRequest("/api/settings", "GET", userId, (params || {}), function(data) {
                if (data) {
                    callback(data);
                    sessionStorage.setItem(sessionConfigKey, JSON.stringify(data));
                } else {
                    callback({
                        "error": i18next.t("no data returned")
                    });
                }
            });

        }
    }
};

var tnthDates = {
    /** validateDateInputFields  check whether the date is a sensible date in month, day and year fields.
     ** params: month, day and year fields and error field ID
     ** NOTE this can replace the custom validation check; hook this up to the onchange/blur event of birthday field
     ** work better in conjunction with HTML5 native validation check on the field e.g. required, pattern match  ***/
    "validateDateInputFields": function(monthField, dayField, yearField, errorFieldId) {
        var m = $(monthField).val();
        var d = $(dayField).val();
        var y = $(yearField).val();
        if (m && d && y) {
            if ($(yearField).get(0).validity.valid && $(monthField).get(0).validity.valid && $(dayField).get(0).validity.valid) {
                m = parseInt(m);
                d = parseInt(d);
                y = parseInt(y);
                var errorField = $("#" + errorFieldId);

                if (!(isNaN(m)) && !(isNaN(d)) && !(isNaN(y))) {
                    var today = new Date();
                    // Check to see if this is a real date
                    var date = new Date(y, m - 1, d);
                    if (!(date.getFullYear() == y && (date.getMonth() + 1) == m && date.getDate() == d)) {
                        errorField.html(i18next.t("Invalid date. Please try again.")).show();
                        return false;
                    } else if (date.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                        errorField.html(i18next.t("Date must not be in the future. Please try again.")).show();
                        return false; //shouldn't be in the future
                    } else if (y < 1900) {
                        errorField.html(i18next.t("Date must not be before 1900. Please try again.")).show();
                        return false;
                    }

                    errorField.html("").hide();

                    return true;

                } else return false;
            } else {
                return false;
            }

        } else {
            return false;
        }
    },
    /***
     * changeFormat - changes date format, particularly for submitting to server
     * @param currentDate - date to change
     * @param reverse - use to switch from yyyy-mm-dd to dd/mm/yyyy
     * @param shorten - removes padding from zeroes (only in reverse)
     * @returns - a date as a string
     *
     * Examples:
     * changeFormat("29/04/2016") returns "2016-04-29T07:00:00", converts according to getTimezoneOffset
     * changeFormat("2016-04-29",true) returns "29/04/2016"
     * changeFormat("2016-04-29",true,true) returns "29/04/2016"
     ***/
    "changeFormat": function(currentDate, reverse, shorten) {
        if (currentDate == null || currentDate == "") {
            return null;
        }
        var yearToPass, convertDate, dateFormatArray;
        if (reverse) {
            dateFormatArray = currentDate.split("-");
            if (!dateFormatArray || (dateFormatArray.length == 0)) return null;
            yearToPass = dateFormatArray[0];
            if (shorten) {
                dateFormatArray[1] = dateFormatArray[1].replace(/^0+/, "");
                dateFormatArray[2] = dateFormatArray[2].replace(/^0+/, "");
            }
            convertDate = dateFormatArray[2] + "/" + dateFormatArray[1] + "/" + yearToPass;
        } else {
            dateFormatArray = currentDate.split("/");
            if (!dateFormatArray || (dateFormatArray.length == 0)) return null;
            // If patient manuals enters two digit year, then add 19 or 20 to year.
            // TODO - this is susceptible to Y2K for 2100s. Be better to force
            // user to type 4 digits.
            var currentTime = new Date();
            if (dateFormatArray[2].length == 2) {
                var shortYear = currentTime.getFullYear().toString().substr(2, 2);
                if (dateFormatArray[2] > shortYear) {
                    yearToPass = "19" + dateFormatArray[2];
                } else {
                    yearToPass = "20" + dateFormatArray[2];
                }
            } else {
                yearToPass = dateFormatArray[2];
            }
            convertDate = yearToPass + "-" + dateFormatArray[1] + "-" + dateFormatArray[0];
            // add T according to timezone
            var tzOffset = currentTime.getTimezoneOffset(); //minutes
            tzOffset /= 60; //hours
            if (tzOffset < 10) tzOffset = "0" + tzOffset;
            convertDate += "T" + tzOffset + ":00:00";
        }
        return convertDate;
    },
    /**
     * Simply swaps:
     *      a/b/cdef to b/a/cdef
     *      (single & double digit permutations accepted...)
     *      ab/cd/efgh to cd/ab/efgh
     * Does not check for valid dates on input or output!
     * @param currentDate string eg 7/4/1976
     * @returns string eg 4/7/1976
     */
    "swap_mm_dd": function(currentDate) {
        var splitDate = currentDate.split("/");
        return splitDate[1] + "/" + splitDate[0] + "/" + splitDate[2];
    },
    /**
     * Convert month string to numeric
     *
     */

    "convertMonthNumeric": function(month) {
        if (!month) return "";
        else {
            var month_map = {
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            };
            var m = month_map[month.toLowerCase()];
            return m ? m : "";
        }
    },
    /**
     * Convert month string to text
     *
     */
    "convertMonthString": function(month) {
        if (!month) return "";
        else {
            var numeric_month_map = {
                1: "Jan",
                2: "Feb",
                3: "Mar",
                4: "Apr",
                5: "May",
                6: "Jun",
                7: "Jul",
                8: "Aug",
                9: "Sep",
                10: "Oct",
                11: "Nov",
                12: "Dec"
            };
            var m = numeric_month_map[parseInt(month)];
            return m ? m : "";
        }
    },
    "isDate": function(obj) {
        return Object.prototype.toString.call(obj) === "[object Date]" && !isNaN(obj.getTime());
    },
    "displayDateString": function(m, d, y) {
        var s = "";
        if (d) s = d;
        if (m) s += (s ? " " : "") + this.convertMonthString(m);
        if (y) s += (s ? " " : "") + y;
        return s;
    },
    /***
     * parseDate - Fancier function for changing javascript date yyyy-mm-dd (with optional time) to a dd/mm/yyyy (optional time) format. Used with mPOWEr
     * @param date - the date to be converted
     * @param noReplace - prevent replacing any spaces with "T" to get in proper javascript format. 2016-02-24 15:28:09-0800 becomes 2016-02-24T15:28:09-0800
     * @param padZero - if true, will add padded zero to month and date
     * @param keepTime - if true, will output the time as part of the date
     * @param blankText - pass a value to display if date is null
     * @returns date as a string with optional time
     *
     * parseDate("2016-02-24T15:28:09-0800",true,false,true) returns "24/2/2016 3:28pm"
     */
    "parseDate": function(date, noReplace, padZero, keepTime, blankText) {
        if (date == null) {
            if (blankText) {
                return blankText;
            } else {
                return "";
            }
        }
        // Put date in proper javascript format
        if (noReplace == null) {
            date = date.replace(" ", "T");
        }
        // Need to reformat dates b/c of date format issues in Safari (and others?)
        // http://stackoverflow.com/questions/6427204/date-parsing-in-javascript-is-different-between-safari-and-chrome
        var a = date.split(/[^0-9]/);
        var toConvert;
        if (a[3]) {
            toConvert = new Date(a[0], a[1] - 1, a[2], a[3], a[4], a[5]);
        } else {
            toConvert = new Date(a[0], a[1] - 1, a[2]);
        }

        // Switch date to mm/dd/yyyy
        //var toConvert = new Date(Date.parse(date));
        var month = toConvert.getMonth() + 1;
        var day = toConvert.getDate();
        if (padZero) {
            if (month <= 9)
                month = "0" + month;
            if (day <= 9)
                day = "0" + day;
        }
        if (keepTime) {
            var amPm = "am";
            var hour = a[3];
            if (a[3] > 11) {
                amPm = "pm";
                if (a[3] > 12) {
                    hour = (a[3] - 12);
                }
            }
            return day + "/" + month + "/" + toConvert.getFullYear() + " " + hour + ":" + a[4] + amPm;
        } else {
            return day + "/" + month + "/" + toConvert.getFullYear();
        }
    },
    /***
     * parseForSorting - changes date to a YYYYMMDDHHMMSS string for sorting (note that this is a string rather than a number)
     * @param date - the date to be converted
     * @param noReplace - prevent replacing any spaces with "T" to get in proper javascript format. 2016-02-24 15:28:09-0800 becomes 2016-02-24T15:28:09-0800. Adding T indicates UTC time
     * @returns date as a string used by system for sorting
     *
     * parseDate("2016-02-24T15:28:09-0800",true) returns "201600224152809"
     */
    "parseForSorting": function(date, noReplace) {
        if (date == null) {
            return "";
        }
        // Put date in proper javascript format
        if (noReplace == null) {
            date = date.replace(" ", "T");
        }
        // Need to reformat dates b/c of date format issues in Safari (and others?)
        // http://stackoverflow.com/questions/6427204/date-parsing-in-javascript-is-different-between-safari-and-chrome
        var a = date.split(/[^0-9]/);
        var toConvert = new Date(a[0], a[1] - 1, a[2], a[3], a[4], a[5]);
        // Switch date to mm/dd/yyyy
        //var toConvert = new Date(Date.parse(date));
        var month = toConvert.getMonth() + 1;
        var day = toConvert.getDate();
        if (month <= 9)
            month = "0" + month;
        if (day <= 9)
            day = "0" + day;
        return toConvert.getFullYear() + month + day + a[3] + a[4] + a[5];

    },
    /***
     * spellDate - spells out date in a format based on language/local. Currently not in use.
     * @param passDate - date to use. If empty, defaults to today.
     * @param ymdFormat - false by default. false = dd/mm/yyyy. true = yyyy-mm-dd
     * @returns spelled out date, localized
     */
    "spellDate": function(passDate, ymdFormat) {
        var todayDate = new Date();
        if (passDate) {
            // ymdFormat is true, we are assuming it's being received as YYYY-MM-DD
            if (ymdFormat) {
                todayDate = passDate.split("-");
                todayDate = new Date(todayDate[2], todayDate[0] - 1, todayDate[1]);
            } else {
                // Otherwide dd/mm/yyyy
                todayDate = passDate.split("/");
                todayDate = new Date(todayDate[2], todayDate[1] - 1, todayDate[0]);
            }
        }
        var returnDate;
        var monthNames = ["January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ];
        // If user's language is Spanish then use dd/mm/yyyy format and changes words
        if (userSetLang !== undefined && userSetLang == "es_MX") {
            monthNames = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
            returnDate = ("0" + todayDate.getDate()).slice(-2) + " de " + monthNames[todayDate.getMonth()] + " de " + todayDate.getFullYear();
        } else if (userSetLang !== undefined && userSetLang == "en_AU") {
            returnDate = ("0" + todayDate.getDate()).slice(-2) + " " + monthNames[todayDate.getMonth()] + " " + todayDate.getFullYear();
        } else {
            returnDate = monthNames[todayDate.getMonth()] + " " + ("0" + todayDate.getDate()).slice(-2) + ", " + todayDate.getFullYear();
        }
        return returnDate;
    },
    /***
     * Calculates number of days between two dates. Used in mPOWEr for surgery/discharge
     * @param startDate - required. Assumes YYYY-MM-DD. This is typically the date of surgery or discharge
     * @param dateToCalc - optional. If empty, then assumes today's date
     * @returns number of days
     */
    "getDateDiff": function(startDate, dateToCalc) {
        var a = startDate.split(/[^0-9]/);
        var dateTime = new Date(a[0], a[1] - 1, a[2]).getTime();
        var d;
        if (dateToCalc) {
            var c = dateToCalc.split(/[^0-9]/);
            d = new Date(c[0], c[1] - 1, c[2]).getTime();
        } else {
            // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime();
        }
        // Round down to floor so we don't add an extra day if session is 12+ hours into the day
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24));
    },
    "getAge": function(birthDate, otherDate) {
        birthDate = new Date(birthDate);
        // Use today's date to calc, unless otherwise specified
        var secondDate = new Date();
        if (otherDate) {
            secondDate = new Date(otherDate);
        }
        var years = (secondDate.getFullYear() - birthDate.getFullYear());

        if (secondDate.getMonth() < birthDate.getMonth() ||
            secondDate.getMonth() == birthDate.getMonth() && secondDate.getDate() < birthDate.getDate()) {
            years--;
        }
        return years;
    },
    /***
     * Simple function to add "days" label to a number of days. Not localized, used for mPOWEr
     * @param dateVal - required. Often derived via getDateDiff
     * @returns {string}
     */
    "addDays": function(dateVal) {
        var toReturn = "N/A";
        if (dateVal && typeof dateVal != undefined) {
            if (dateVal == 1) {
                toReturn = "1 day";
            } else if (dateVal < 0) {
                toReturn = "--";
            } else {
                toReturn = dateVal + " days";
            }
        } else if (dateVal === 0) {
            toReturn = "Today";
        }
        return toReturn;
    },
    "isValidDefaultDateFormat": function(date, errorField) {
        if (!hasValue(date)) return false;
        if (date.length < 10) return false;
        var dArray = $.trim(date).split(" ");
        if (dArray.length < 3) return false;
        var day = dArray[0],
            month = dArray[1],
            year = dArray[2];
        if (day.length < 1) return false;
        if (month.length < 3) return false;
        if (year.length < 4) return false;
        if (!/(0)?[1-9]|1\d|2\d|3[01]/.test(day)) return false;
        if (!/jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/i.test(month)) return false;
        if (!/(19|20)\d{2}/.test(year)) return false;
        var dt = new Date(date);
        if (!this.isDateObj(dt)) return false;
        else if (!this.isValidDate(year, this.convertMonthNumeric(month), day)) {
            return false;
        } else {
            var today = new Date(),
                errorMsg = "";
            if (dt.getFullYear() < 1900) errorMsg = "Year must be after 1900";
            // Only allow if date is before today
            if (dt.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                errorMsg = "The date must not be in the future.";
            }
            if (errorMsg) {
                if (errorField) $(errorField).text(errorMsg);
                return false;
            } else {
                if (errorField) $(errorField).text("");
                return true;
            }
        }
    },
    "isDateObj": function(d) {
        return Object.prototype.toString.call(d) === "[object Date]" && !isNaN(d.getTime());
    },
    "isValidDate": function(y, m, d) {
        var date = this.getDateObj(y, m, d);
        var convertedDate = this.getConvertedDate(date);
        var givenDate = this.getGivenDate(y, m, d);
        return (givenDate == convertedDate);
    },
    /*
     * method does not check for valid numbers, will return NaN if conversion failed
     */
    "getDateObj": function(y, m, d, h, mi, s) {
        if (!h) h = 0;
        if (!mi) mi = 0;
        if (!s) s = 0;
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d), parseInt(h), parseInt(mi), parseInt(s));
    },
    "getConvertedDate": function(dateObj) {
        if (dateObj && this.isDateObj(dateObj)) return "" + dateObj.getFullYear() + (dateObj.getMonth() + 1) + dateObj.getDate();
        else return "";
    },
    "getGivenDate": function(y, m, d) {
        return "" + y + m + d;
    },
    /*
     * NB For dateString in ISO-8601 format date as returned from server e.g. '2011-06-29T16:52:48'*/
    "formatDateString": function(dateString, format) {
        if (dateString) {
            var iosDateTest = /^([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3([12]\d|0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-9]|0[1-9]\d|[12]\d{2}|3([0-5]\d|6[1-6])))([T\s]((([01]\d|2[0-3])((:?)[0-5]\d)?|24\:?00)([\.,]\d+(?!:))?)?(\17[0-5]\d([\.,]\d+)?)?([zZ]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?)?)?$/;
            var d = new Date(dateString);
            var day, month, year, hours, minutes, seconds, nd;
            //note instantiating ios formatted date using Date object resulted in error in IE
            if (!iosDateTest && !isNaN(d) && !this.isDateObj(d)) return "";
            if (iosDateTest.test(dateString)) {
                //IOS date, no need to convert again to date object, just parse it as is
                //issue when passing it into Date object, the output date is inconsistent across from browsers
                var dArray = $.trim($.trim(dateString).replace(/[\.TZ:\-]/gi, " ")).split(" ");
                year = dArray[0];
                month = dArray[1];
                day = dArray[2];
                hours = dArray[3] || "0";
                minutes = dArray[4] || "0";
                seconds = dArray[5] || "0";
            } else {
                day = d.getDate();
                month = d.getMonth() + 1;
                year = d.getFullYear();
                hours = d.getHours();
                minutes = d.getMinutes();
                seconds = d.getSeconds();
                nd = "";
            }
            var pad = function(n) {n = parseInt(n); return (n < 10) ? "0" + n : n;};
            day = pad(day);
            month = pad(month);
            hours = pad(hours);
            minutes = pad(minutes);
            seconds = pad(seconds);

            switch (format) {
            case "mm/dd/yyyy":
                nd = month + "/" + day + "/" + year;
                break;
            case "mm-dd-yyyy":
                nd = month + "-" + day + "-" + year;
                break;
            case "mm-dd-yyyy hh:mm:ss":
                nd = month + "-" + day + "-" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "dd/mm/yyyy":
                nd = day + "/" + month + "/" + year;
                break;
            case "dd/mm/yyyy hh:mm:ss":
                nd = day + "/" + month + "/" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "dd-mm-yyyy":
                nd = day + "-" + month + "-" + year;
                break;
            case "dd-mm-yyyy hh:mm:ss":
                nd = day + "-" + month + "-" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "iso-short":
            case "yyyy-mm-dd":
                nd = year + "-" + month + "-" + day;
                break;
            case "iso":
            case "yyyy-mm-dd hh:mm:ss":
                nd = year + "-" + month + "-" + day + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "d M y hh:mm:ss":
                nd = this.displayDateString(month, day, year);
                nd = nd + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "d M y":
                nd = this.displayDateString(month, day, year);
                break;
            default:
                nd = this.displayDateString(month, day, year);
                break;
            }

            return nd;
        } else return "";
    },
    "convertToLocalTime": function(dateString) {
        var convertedDate = "";
        //assuming dateString is UTC date/time
        if (dateString) {
            var d = new Date(dateString);
            var newDate = new Date(d.getTime() + d.getTimezoneOffset() * 60 * 1000);
            var offset = d.getTimezoneOffset() / 60;
            var hours = d.getHours();
            newDate.setHours(hours - offset);
            var options = {
                year: "numeric",
                day: "numeric",
                month: "short",
                hour: "numeric",
                minute: "numeric",
                second: "numeric",
                hour12: false
            };
            convertedDate = newDate.toLocaleString(options);
        }
        return convertedDate;
    },
    "getUserTimeZone": function(userId) {
        var selectVal = $("#profileTimeZone").length > 0 ? $("#profileTimeZone option:selected").val() : "";
        var userTimeZone = "";
        if (selectVal == "") {
            if (userId) {
                tnthAjax.sendRequest("/api/demographics/" + userId, "GET", userId, {
                    sync: true
                }, function(data) {
                    if (!data.error) {
                        if (data) {
                            data.extension.forEach(
                                function(item) {
                                    if (item.url === SYSTEM_IDENTIFIER_ENUM.timezone) {
                                        userTimeZone = item.timezone;
                                    }
                                });
                        }
                    } else {
                        userTimeZone = "UTC";
                    }
                });
            }
        } else {
            userTimeZone = selectVal;
        }
        return (userTimeZone || "UTC");
    },
    "localeSessionKey": "currentUserLocale",
    "clearSessionLocale": function() {
        sessionStorage.removeItem(this.localeSessionKey);
    },
    "getUserLocale": function(force) {
        var sessionKey = this.localeSessionKey;
        var sessionLocale = sessionStorage.getItem(sessionKey);
        var locale = "";
        if (!force && sessionLocale) {
            return sessionLocale;
        } else {
            this.clearSessionLocale();
            $.ajax({
                type: "GET",
                url: "/api/me",
                async: false
            }).done(function(data) {
                var userId = "";
                if (data) {
                    userId = data.id;
                }
                if (userId) {
                    tnthAjax.sendRequest("/api/demographics/" + userId, "GET", userId, {
                        sync: true
                    }, function(data) {
                        if (!data.error) {
                            if (data && data.communication) {
                                data.communication.forEach(function(item) {
                                    if (item.language) {
                                        locale = item.language.coding[0].code;
                                        sessionStorage.setItem(sessionKey, locale);
                                    }
                                });
                            }
                        } else {
                            locale = "en_us";
                        }
                    });
                }
            }).fail(function() {});
        }
        if (!locale) {
            locale = "en_us";
        }
        return locale;
    },
    getDateWithTimeZone: function(dObj) {
        /*
         * param is a date object - calculating UTC date using Date object's timezoneOffset method
         * the method return offset in minutes, so need to convert it to miliseconds - adding the resulting offset will be the UTC date/time
         */
        var utcDate = new Date(dObj.getTime() + (dObj.getTimezoneOffset()) * 60 * 1000);
        //I believe this is a valid python date format, will save it as GMT date/time NOTE, conversion already occurred, so there will be no need for backend to convert it again
        return tnthDates.formatDateString(utcDate, "yyyy-mm-dd hh:mm:ss");
    },
    /*
     * return object containing today's date/time information
     */
    getTodayDateObj: function() {
        var today = new Date();
        var td = today.getDate(),
            tm = today.getMonth() + 1,
            ty = today.getFullYear();
        var th = today.getHours(),
            tmi = today.getMinutes(),
            ts = today.getSeconds();
        var gmtToday = this.getDateWithTimeZone(this.getDateObj(ty, tm, td, th, tmi, ts));
        var pad = function(n) {n = parseInt(n); return (n < 10) ? "0" + n : n;};
        return {
            date: today,
            day: td,
            month: tm,
            year: ty,
            hour: th,
            minute: tmi,
            second: ts,
            displayDay: pad(td),
            displayMonth: pad(tm),
            displayYear: pad(ty),
            displayHour: pad(th),
            displayMinute: pad(tmi),
            displaySecond: pad(ts),
            gmtDate: gmtToday
        };
    },
    /*
     * parameters: day, month and year values in numeric, boolean value for restrictToPresent, true if the date needs to be before today, false is the default
     */
    dateValidator: function(day, month, year, restrictToPresent) {
        var errorMessage = "";
        if (day && month && year) {
            // Check to see if this is a real date
            var iy = parseInt(year),
                im = parseInt(month),
                iid = parseInt(day);
            var date = new Date(iy, im - 1, iid);

            if (date.getFullYear() == iy && (date.getMonth() + 1) == im && date.getDate() == iid) {
                if (iy < 1900) {
                    errorMessage = i18next.t("Year must be after 1900");
                }
                // Only allow if date is before today
                if (restrictToPresent) {
                    var today = new Date();
                    if (date.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                        errorMessage = i18next.t("The date must not be in the future.");
                    }
                }
            } else {
                errorMessage = i18next.t("Invalid Date. Please enter a valid date.");
            }
        } else {
            errorMessage = i18next.t("Missing value.");
        }
        return errorMessage;
    }

};

/***
 * Bootstrap datatables functions
 * Uses http://bootstrap-table.wenzhixin.net.cn/documentation/
 ****/

var tnthTables = {
    /***
     * Quick way to sort when text is wrapper in an <a href> or other tag
     * @param a,b - the two items to compare
     * @returns 1,-1 or 0 for sorting
     */
    "stripLinksSorter": function(a, b) {
        a = $(a).text();
        b = $(b).text();
        var aa = parseFloat(a);
        var bb = parseFloat(b);
        return bb - aa;
    },
    /***
     * Quick way to sort when text is wrapped in an <a href> or other tag
     * NOTE for text that is NOT number
     * @param a,b - the two items to compare
     * @returns 1,-1 or 0 for sorting
     */
    "stripLinksTextSorter": function(a, b) {
        var aa = $(a).text();
        var bb = $(b).text();
        if (aa < bb) return -1;
        if (aa > bb) return 1;
        return 0;
    },
    /***
     * sorting date string,
     * @param a,b - the two items to compare - note, this assumes that the parameters
     * are in valid date format e.g. 3 August 2017
     * @returns 1,-1 or 0 for sorting
     */
    "dateSorter": function(a, b) {
        if (!(a)) a = 0;
        if (!(b)) b = 0;
        /*
         * make sure the string passed in does not have line break element if so it is a possible mult-line text, split it up and use
         * the first item in the resulting array
         */
        var regex = /<br\s*[\/]?>/gi;
        a = a.replace(regex, "\n");
        b = b.replace(regex, "\n");
        var ar = a.split("\n");
        if (ar.length > 0) a = ar[0];
        var br = b.split("\n");
        if (br.length > 0) b = br[0];
        /* note getTime returns the numeric value corresponding to the time for the specified date according to universal time
         * therefore, can be used for sorting
         */
        var a_d = (new Date(a)).getTime();
        var b_d = (new Date(b)).getTime();

        if (isNaN(a_d)) a_d = 0;
        if (isNaN(b_d)) b_d = 0;

        return b_d - a_d;
    },
    /***
     * sorting alpha numeric string
     */
    "alphanumericSorter": function(a, b) {
        /*
         * see https://cdn.rawgit.com/myadzel/6405e60256df579eda8c/raw/e24a756e168cb82d0798685fd3069a75f191783f/alphanum.js
         */
        return alphanum(a, b);
    }
};

var Global = {
    "registerModules": function() { //TODO use webpack or requireJS to import modules?
        if (!window.portalModules) {
            window.portalModules = {};
        }
        window.portalModules.tnthAjax = tnthAjax;
        window.portalModules.tnthDates = tnthDates;
        window.portalModules.assembleContent = assembleContent;
        window.portalModules.orgTool = OrgTool;
        window.portalModules.i18next = i18next;
    },
    "initPortalWrapper": function(PORTAL_NAV_PAGE, callback) {
        var isIE = getIEVersion();
        callback = callback || function() {};
        if (isIE) {
            newHttpRequest(PORTAL_NAV_PAGE, function(data) { //support IE9 or earlier
                embed_page(data);
                tnthAjax.initNotifications(function(data) { //ajax to get notifications information
                    Global.notifications(data);
                });
                callback();
            }, true);
        } else {
            funcWrapper(PORTAL_NAV_PAGE, function(data) {
                embed_page(data);
                tnthAjax.initNotifications(function(data) { //ajax to get notifications information
                    Global.notifications(data);
                });
                callback();
            });
        }
    },
    "loginAs": function() {
        var LOGIN_AS_PATIENT = (typeof sessionStorage !== "undefined") ? sessionStorage.getItem("loginAsPatient") : null;
        if (LOGIN_AS_PATIENT) {
            sessionStorage.clear();
            tnthDates.getUserLocale(true); //need to clear current user locale in session storage when logging in as patient
            if (typeof history !== "undefined" && history.pushState) {
                history.pushState(null, null, location.href);
            }
            window.addEventListener("popstate", function() {
                if (typeof history !== "undefined" && history.pushState) {
                    history.pushState(null, null, location.href);
                } else {
                    window.history.forward(1);
                }
            });
        }
    },
    "footer": function() {
        var logoLinks = $("#homeFooter .logo-link");
        if (logoLinks.length > 0) {
            logoLinks.each(function() {
                if (!$.trim($(this).attr("href"))) {
                    $(this).removeAttr("target");
                    $(this).on("click", function(e) {
                        e.preventDefault();
                        return false;
                    });
                }
            });
        }
        setTimeout(function() { //Reveal footer after load to avoid any flashes will above content loads
            $("#homeFooter").show();
        }, 100);

        setTimeout(function() {
            var userLocale = $("#copyrightLocaleCode").val();
            var footerElements = "footer .copyright, #homeFooter .copyright, .footer-container .copyright";
            var getContent = function(cc) {
                var content = "";
                switch (String(cc.toUpperCase())) {
                case "US":
                case "EN_US":
                    content = i18next.t("&copy; 2017 Movember Foundation. All rights reserved. A registered 501(c)3 non-profit organization (Movember Foundation).");
                    break;
                case "AU":
                case "EN_AU":
                    content = i18next.t("&copy; 2017 Movember Foundation. All rights reserved. Movember Foundation is a registered charity in Australia ABN 48894537905 (Movember Foundation).");
                    break;
                case "NZ":
                case "EN_NZ":
                    content = i18next.t("&copy; 2017 Movember Foundation. All rights reserved. Movember Foundation is a New Zealand registered charity number CC51320 (Movember Foundation).");
                    break;
                default:
                    content = i18next.t("&copy; 2017 Movember Foundation (Movember Foundation). All rights reserved.");

                }
                return content;

            };
            if (userLocale) {
                $(footerElements).html(getContent(userLocale));
            } else {
                $.getJSON("//freegeoip.net/json/?callback=?", function(data) {
                    if (data && data.country_code) { //country code Australia AU New Zealand NZ USA US
                        $(footerElements).html(getContent(data.country_code));
                    } else {
                        $(footerElements).html(getContent());
                    }
                });
            }
        }, 500);
    },
    "notifications": function(data) {
        if (data && data.notifications) {
            var notificationText = "";
            (data.notifications).forEach(function(notice) {
                notificationText += "<div class='notification' data-id='" + notice.id + "' data-name='" + notice.name + "'>" + i18next.t(notice.content) + "</div>";
            });
            var setVis = function() {
                var allVisited = true;
                var doHideCloseButton = true;
                $("#notificationBanner [data-id]").each(function() {
                    var actionRequired = $(this).find("[data-action-required]").length > 0;
                    if (!actionRequired) { //close button should not be hidden if there is any link that does not require user action
                        if (allVisited && !$(this).attr("data-visited")) { //check if all links have been visited
                            allVisited = false;
                        }
                        if (!$(this).attr("data-visited")) { //don't hide the close button if there one link that hasn't been visited
                            doHideCloseButton = false;
                        }
                    } else {
                        allVisited = false;
                    }
                });
                if (allVisited) {
                    $("#notificationBanner").hide();
                } else {
                    if (doHideCloseButton) {
                        $("#notificationBanner .close").removeClass("active");
                    }
                }
            };
            if (notificationText) {
                $("#notificationBanner .content").html(notificationText);
                $("#notificationBanner .notification").addClass("active");
                $("#notificationBanner").show();
                $("#notificationBanner [data-id] a").each(function() {
                    $(this).on("click", function() {
                        var parentElement = $(this).closest(".notification");
                        /*
                         *  adding the attribute data-visited will hide the notification entry
                         */
                        parentElement.attr("data-visited", "true");
                        //delete relevant notification
                        tnthAjax.deleteNotification($("#notificationUserId").val(), parentElement.attr("data-id"));
                    });
                });
                $("#notificationBanner [data-id]").each(function() {
                    var actionRequired = $(this).find("[data-action-required]").length > 0;
                    if (!actionRequired) {
                        /*
                         * adding the class of active will allow close button to display
                         */
                        $("#notificationBanner .close").addClass("active");
                    }
                    $(this).on("click", function(e) {
                        e.stopPropagation();
                        setVis();
                    });
                });
                $("#notificationBanner .close").on("click", function(e) {
                    //closing the banner
                    e.stopPropagation();
                    $("#notificationBanner [data-id]").each(function() {
                        var actionRequired = $(this).find("[data-action-required]").length > 0;
                        if (!actionRequired) {
                            tnthAjax.deleteNotification($("#notificationUserId").val(), $(this).attr("data-id"));
                            $(this).attr("data-visited", "true");
                        }
                    });
                    setVis();
                });
            } else {
                $("#notificationBanner").hide();
            }
        } else {
            $("#notificationBanner").hide();
        }
    }
};

var userSetLang = tnthDates.getUserLocale();
Global.registerModules();
var i18next = window.portalModules.i18next;
__i18next.init({
    "lng": userSetLang
}, function() {
    $(document).ready(function() {

        if ($("#alertModal").length > 0) {
            $("#alertModal").modal("show");
        }
        tnthAjax.beforeSend();
        Global.footer();
        Global.loginAs();

        var PORTAL_NAV_PAGE = window.location.protocol + "//" + window.location.host + "/api/portal-wrapper-html/";

        if (PORTAL_NAV_PAGE) {
            loader(true);
            Global.initPortalWrapper(PORTAL_NAV_PAGE);
        } else {
            loader();
        }
        // To validate a form, add class to <form> and validate by ID.
        $("form.to-validate").validator({
            custom: {
                birthday: function() {
                    var m = parseInt($("#month").val());
                    var d = parseInt($("#date").val());
                    var y = parseInt($("#year").val());
                    // If all three have been entered, run check
                    var goodDate = true;
                    var errorMsg = "";
                    // If NaN then the values haven't been entered yet, so we
                    // validate as true until other fields are entered
                    if (isNaN(y) || (isNaN(d) && isNaN(y))) {
                        $("#errorbirthday").html(i18next.t("All fields must be complete.")).hide();
                        goodDate = false;
                    } else if (isNaN(d)) {
                        errorMsg = i18next.t("Please enter a valid date.");
                    } else if (isNaN(m)) {
                        errorMsg += (errorMsg ? "<br/>" : "") + i18next.t("Please enter a valid month.");
                    } else if (isNaN(y)) {
                        errorMsg += (errorMsg ? "<br/>" : "") + i18next.t("Please enter a valid year.");
                    }

                    if (errorMsg) {
                        $("#errorbirthday").html(errorMsg).show();
                        $("#birthday").val("");
                        goodDate = false;
                    }
                    if (goodDate) {
                        $("#errorbirthday").html("").hide();
                    }

                    return goodDate;
                },
                customemail: function($el) {
                    var emailVal = $.trim($el.val());
                    var update = function($el) {
                        if ($el.attr("data-update-on-validated") === "true" && $el.attr("data-user-id")) {
                            assembleContent.demo($el.attr("data-user-id"), true, $el);
                        }
                    };
                    if (emailVal === "") {
                        if ($el.attr("data-optional")) {
                            /*
                             * if email address is optional, update it as is
                             */
                            update($el);
                            return true;
                        } else {
                            return false;
                        }
                    }
                    var emailReg = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                    // Add user_id to api call (used on patient_profile page so that staff can edit)
                    var addUserId = "";
                    if ($el.attr("data-user-id")) {
                        addUserId = "&user_id=" + $el.attr("data-user-id");
                    }
                    if (emailReg.test(emailVal)) {  // If this is a valid address, then use unique_email to check whether it's already in use
                        tnthAjax.sendRequest("/api/unique_email?email=" + encodeURIComponent(emailVal) + addUserId, "GET", "", null, function(data) {
                            if (!data.error) {
                                if (data.unique) {
                                    $("#erroremail").html("").parents(".form-group").removeClass("has-error");
                                    update($el);
                                } else {
                                    $("#erroremail").html(i18next.t("This e-mail address is already in use. Please enter a different address.")).parents(".form-group").addClass("has-error");
                                }

                            }
                        });
                    }
                    return emailReg.test(emailVal);
                },
                htmltags: function($el) {
                    var containHtmlTags = function(text) {
                        if (!(text)) {return false;}
                        return /[<>]/.test(text);
                    };
                    var invalid = containHtmlTags($el.val());
                    if (invalid) $("#error" + $el.attr("id")).html("Invalid characters in text.");
                    else $("#error" + $el.attr("id")).html("");
                    return !invalid;
                }
            },
            errors: {
                htmltags: i18next.t("Please remove invalid characters and try again."),
                birthday: i18next.t("Sorry, this isn't a valid date. Please try again."),
                customemail: i18next.t("This isn't a valid e-mail address, please double-check.")
            },
            disable: false
        }).off("input.bs.validator change.bs.validator"); // Only check on blur (turn off input)   to turn off change - change.bs.validator
    });
});
