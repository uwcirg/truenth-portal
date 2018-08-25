/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/
var DELAY_LOADING = false;
var SYSTEM_IDENTIFIER_ENUM = {
    "external_study_id": "http://us.truenth.org/identity-codes/external-study-id",
    "external_site_id": "http://us.truenth.org/identity-codes/external-site-id",
    "practice_region": "http://us.truenth.org/identity-codes/practice-region",
    "race": "http://hl7.org/fhir/StructureDefinition/us-core-race",
    "race_system": "http://hl7.org/fhir/v3/Race",
    "ethnicity": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
    "ethnicity_system": "http://hl7.org/fhir/v3/Ethnicity",
    "indigenous": "http://us.truenth.org/fhir/StructureDefinition/AU-NHHD-METeOR-id-291036",
    "timezone": "http://hl7.org/fhir/StructureDefinition/user-timezone",
    "language": "http://hl7.org/fhir/valueset/languages",
    "language_system": "urn:ietf:bcp:47",
    "shortname": "http://us.truenth.org/identity-codes/shortname",
    SNOMED_SYS_URL: "http://snomed.info/sct",
    CLINICAL_SYS_URL: "http://us.truenth.org/clinical-codes",
    CANCER_TREATMENT_CODE: "118877007",
    NONE_TREATMENT_CODE: "999"
};
var CLINICAL_CODE_ENUM = {
    "biopsy": {
        code: "111",
        display: "biopsy"
    },
    "pca_diag": {
        code: "121",
        display: "PCa diagnosis"
    },
    "pca_localized": {
        code: "141",
        display: "PCa localized diagnosis"
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
    if (userId) { this.setUserId(userId); }
    if (doPopulateUI) { this.populateUI(); }
    $("#userOrgs input[name='organization']").each(function() {
        $(this).prop("checked", false);
    });
    $("#clinics").attr("loaded", true);
};
OrgTool.prototype.setUserId = function(userId) {
    $("#fillOrgs").attr("userId", userId);
};
OrgTool.prototype.getUserId = function() {
    return $("#fillOrgs").attr("userId");
};
OrgTool.prototype.inArray = function(n, array) {
    if (!n || !array || !Array.isArray(array)) { return false; }
    var found = false;
    for (var index = 0; !found && index < array.length; index++) {
        found = String(array[index]) === String(n);
    }
    return found;
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
OrgTool.prototype.getOrgName = function(orgId) {
    var orgsList = this.getOrgsList();
    if (orgId && orgsList.hasOwnProperty(orgId)) {
        return orgsList[orgId].name;
    }
    else { return ""; }
};
OrgTool.prototype.filterOrgs = function(leafOrgs) {
    if (!leafOrgs) { return false; }
    if (leafOrgs.length === 0) { return false; }
    var self = this;
    $("#fillOrgs input[name='organization']").each(function() {
        if (!self.inArray($(this).val(), leafOrgs)) {
            $(this).hide();
            if (self.orgsList[$(this).val()]) {
                var l = $(this).closest("label");
                if (self.orgsList[$(this).val()].children.length === 0) {
                    l.hide();
                } else {
                    l.addClass("data-display-only");
                }
            }
        }
    });

    var topList = self.getTopLevelOrgs();
    topList.forEach(function(orgId) {
        var allChildrenHidden = true;
        $("#fillOrgs .org-container[data-parent-id='" + orgId + "']").each(function() {
            var subOrgs = $(this).find(".org-container");
            if (subOrgs.length > 0) {
                var allSubOrgsHidden = true;
                subOrgs.each(function() {
                    var isVisible = false;
                    $(this).find("input[name='organization']").each(function() {
                        if ($(this).is(":visible") || String($(this).css("display")) !== "none") {
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
                        if ($(this).is(":visible") || String($(this).css("display")) !== "none") {
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
OrgTool.prototype.getOrgName = function(orgId) {
    var org = this.orgsList[orgId];
    if (!org) return "";
    return org.name;
};
OrgTool.prototype.populateOrgsList = function(items) {
    var entry = items, self = this, parentId, orgsList = {};
    if (Object.keys(this.orgsList).length === 0) {
        if (!items) { return false; }
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (!orgsList[parentId]) {
                    var o = self.findOrg(entry, parentId);
                    orgsList[parentId] = new OrgObj(o.id, o.name);
                }
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
                    self.TOP_LEVEL_ORGS.push(item.id);
                }
            }
            if (item.extension) {
                orgsList[item.id].extension = item.extension;
            }
            if (item.language) {
                orgsList[item.id].language = item.language;
            }
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
                if (orgsList[item.id]) {
                    orgsList[item.id].parentOrgId = parentId;
                }
            }
        });
        if (items.length > 0) { this.initialized = true; }
        this.orgsList = orgsList;
    }
    return orgsList;
};
OrgTool.prototype.getShortName = function(orgId) {
    var shortName = "";
    if (!orgId) { return shortName; }
    var orgsList = this.getOrgsList();
    var orgItem = orgsList.hasOwnProperty(orgId) ? orgsList[orgId]: null;
    if (orgItem && orgItem.shortname) {
        shortName = orgItem.shortname;
    }
    return shortName;
};
OrgTool.prototype.populateUI = function() {
    if (sessionStorage.orgsHTML) {
        $("#fillOrgs").html(sessionStorage.orgsHTML);
        return true;
    }
    var self = this, container = $("#fillOrgs"), orgsList = this.orgsList, parentContent = "";
    function getState(item) {
        var s = "", found = false;
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
        var orgA = orgsList[a], orgB = orgsList[b];
        if (orgA.name < orgB.name) { return -1; }
        if (orgA.name > orgB.name) { return 1; }
        return 0;
    });
    var parentFragment = document.createDocumentFragment(), parentDiv;
    parentOrgsArray.forEach(function(org) {
        parentDiv = document.createElement("div");
        parentDiv.setAttribute("id", org+"_container");
        var parentOrgItem = orgsList[org];
        if (parentOrgItem.children.length > 0) {
            if ($("#userOrgs legend[orgId='" + org + "']").length === 0) {
                parentDiv.classList.add("parent-org-container");
                parentContent = "<legend orgId='{{orgId}}'>{{orgName}}</legend>" +
                    "<input class='tnth-hide' type='checkbox' name='organization' parent_org='true' data-org-name='{{orgName}}' data-short-name='{{shortName}}' id='{{orgId}}_org' state='{{state}}' value='{{orgId}}' /></div>";
            }
        } else {
            if ($("#userOrgs label[id='org-label-" + org + "']").length === 0) {
                parentDiv.classList.add("parent-org-container", "parent-singleton");
                parentContent = "<label id='org-label-{{orgId}}' class='org-label'>" +
                    "<input class='clinic' type='checkbox' name='organization' parent_org='true' id='{{orgId}}_org' state='{{state}}' value='{{orgId}}' " +
                    "data-parent-id='{{orgId}}'  data-org-name='{{orgName}}' data-short-name='{{shortName}}' data-parent-name='{{orgName}}'/><span>{{orgName}}</span></label></div>";
            }
        }
        parentContent = parentContent.replace(/\{\{orgId\}\}/g, org)
            .replace(/\{\{shortName\}\}/g, (parentOrgItem.shortname || parentOrgItem.name))
            .replace(/\{\{orgName\}\}/g, i18next.t(parentOrgItem.name))
            .replace(/\{\{state\}\}/g, getState(parentOrgItem));
        parentDiv.innerHTML = parentContent;
        parentFragment.appendChild(parentDiv);
    });
    container.get(0).appendChild(parentFragment);
    keys.forEach(function(org) { //draw child orgs
        if (orgsList[org].children.length > 0) { // Fill in each child clinic
            var childClinic = "";
            var items = orgsList[org].children.sort(function(a, b) { // sort child clinic in alphabetical order
                if (a.name < b.name) { return -1; }
                if (a.name > b.name) { return 1; }
                return 0;
            });
            items.forEach(function(item) {
                var _parentOrgId = item.parentOrgId, _parentOrg = orgsList[_parentOrgId];
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
                var attrObj = {dataAttributes:(' data-parent-id="' + topLevelOrgId + '"  data-parent-name="' + orgsList[topLevelOrgId].name + '" '), containerClass: "", textClass: ""};
                if (_isTopLevel) {
                    attrObj.dataAttributes = (' data-parent-id="' + _parentOrgId + '"  data-parent-name="' + _parentOrg.name + '" ');
                }
                if (orgsList[item.id].children.length > 0) {
                    if (_isTopLevel) {
                        attrObj.containerClass = "sub-org-container";
                        attrObj.textClass = "text-muted";
                    } else {
                        attrObj.textClass = "text-muter";
                    }
                } else {
                    if (_isTopLevel) {
                        attrObj.textClass = "text-muted singleton";
                    }
                }
                childClinic = childClinic.replace(/\{\{itemId\}\}/g, item.id)
                    .replace(/\{\{itemName\}\}/g, item.name)
                    .replace(/\{\{shortName\}\}/g, (item.shortname || item.name))
                    .replace(/\{\{state\}\}/g, state ? state : "")
                    .replace(/\{\{dataAttributes\}\}/g, attrObj.dataAttributes)
                    .replace("{{containerClass}}", attrObj.containerClass)
                    .replace(/\{\{textClasses\}\}/g, attrObj.textClass);
                var parentOrgContainer = $("#" + _parentOrgId + "_container");
                if (parentOrgContainer.length > 0) {
                    parentOrgContainer.append(childClinic);
                } else {
                    container.append(childClinic);
                }
            });
        }
    });
    sessionStorage.setItem("orgsHTML", container.html());
    if (!container.text()) {
        container.html(i18next.t("No organizations available"));
    }
};
OrgTool.prototype.getSelectedOrgTopLevelParentOrg = function() {
    return this.getTopLevelParentOrg(this.getSelectedOrg().val());
};
OrgTool.prototype.getSelectedOrg = function() {
    return $("#userOrgs input[name='organization']:checked");
};
OrgTool.prototype.getUserTopLevelParentOrgs = function(uo) {
    var parentList = [], self = this;
    if (uo) {
        if (uo.parentList) { return uo.parentList; }
        uo.forEach(function(o) {
            var p = self.getTopLevelParentOrg(o);
            if (p && !self.inArray(p, parentList)) {
                parentList.push(p);
            }
        });
        uo.parentList = parentList;
        return parentList;
    } else { return false; }
};
OrgTool.prototype.getTopLevelParentOrg = function(currentOrg) {
    if (!currentOrg) { return false; }
    var ml = this.getOrgsList(), currentOrgItem = ml[currentOrg], self = this;
    if (!ml || !currentOrgItem) { return false; }
    if (currentOrgItem.isTopLevel) {
        return currentOrg;
    }
    if (currentOrgItem.parentOrgId) {
        return self.getTopLevelParentOrg(currentOrgItem.parentOrgId);
    }
    return currentOrg;
};
OrgTool.prototype.getChildOrgs = function(orgs, orgList) {
    if (!orgs || (orgs.length === 0)) {
        return orgList;
    } else {
        orgList = orgList || [];
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
    userOrgs = userOrgs || [];
    userOrgs.forEach(function(orgId) {
        here_below_orgs.push(orgId);
        var co = mainOrgsList[orgId], cOrgs = self.getChildOrgs((co && co.children ? co.children : null));
        if (cOrgs && cOrgs.length > 0) {
            here_below_orgs = here_below_orgs.concat(cOrgs);
        }
    });
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
    $("#userOrgs .noOrg-container").hide();
};

var tnthAjax = {
    "beforeSend": function() {
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", $("#__CRSF_TOKEN").val());
                }
            }
        });
    },
    "sendRequest": function(url, method, userId, params, callback) {
        if (!url) { return false; }
        var defaultParams = {type: method ? method : "GET", url: url, attempts: 0, max_attempts: 3, contentType: "application/json; charset=utf-8", dataType: "json", sync: false, timeout: 5000, data: null, useWorker: false, async: true};
        params = params || defaultParams;
        params = $.extend({}, defaultParams, params);
        params.async = params.sync ? false: params.async;
        var self = this;
        var fieldHelper = this.FieldLoaderHelper, targetField = params.targetField || null;
        callback = callback || function() {};
        params.attempts++;
        fieldHelper.showLoader(targetField);
        if (params.useWorker && window.Worker && !_isTouchDevice()) { /*global _isTouchDevice()*/
            initWorker(url, params, function(result) { /*global initWorker*/
                var data;
                try {
                    data = JSON.parse(result);
                } catch(e) {
                    callback({error: "Error occurred parsing data for " + url});
                    return false;
                }
                if (!data) {
                    callback({"error": true, "data": "no data returned"});
                    fieldHelper.showError(targetField);
                } else if (data.error) {
                    callback({"error": true, "data": data});
                    self.sendError(data, url, userId);
                    fieldHelper.showError(targetField);
                } else {
                    callback(data);
                    fieldHelper.showUpdate(targetField);
                }
            });
            return true;
        }
        if (!params.cache) {
            params.headers = {
                "cache-control": "no-cache",
                "expires": "-1",
                "pragma": "no-cache"
            };
        }
        $.ajax(params).done(function(data) {
            params.attempts = 0;
            if (data) {
                fieldHelper.showUpdate(targetField);
                callback(data);
            } else {
                fieldHelper.showError(targetField);
                callback({"error": true, "data": "no data returned"});
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
                fieldHelper.showError(targetField);
                callback({"error": true, "data": xhr});
                self.sendError(xhr, url, userId);
            }
        });
    },
    "sendError": function(xhr, url, userId) {
        if (!xhr) { return false; }
        var errorMessage = "[Error occurred processing request]  status - " + (parseInt(xhr.status) === 0 ? "request timed out/network error" : xhr.status) + ", response text - " + (xhr.responseText ? xhr.responseText : "no response text returned from server");
        tnthAjax.reportError(userId ? userId : "Not available", url, errorMessage, true);
    },
    "reportError": function(userId, page_url, message, sync) {
        //params need to contain the following: subject_id: User on which action is being attempted message: Details of the error event page_url: The page requested resulting in the error
        var params = {};
        params.subject_id = userId ? userId : 0;
        params.page_url = page_url ? page_url : window.location.href;
        params.message = "Error generated in JS - " + (message ? message.replace(/["']/g, "") : "no detail available"); //don't think we want to translate message sent back to the server here
        if (window.console) {
            console.log("Errors occurred.....");
            console.log(params); /*global console*/
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
        delayDuration: 300,
        showLoader: function(targetField) {
            if (!targetField || targetField.length === 0) { return false; }
            var el = $("#" + (targetField.attr("data-save-container-id") || targetField.attr("id")) + "_load");
            el.css("opacity", 1);
            el.closest(".save-loader-wrapper").addClass("loading");
        },
        showUpdate: function(targetField) {
            var __timeout = this.delayDuration;
            if (!targetField || targetField.length === 0) { return false; }
            setTimeout(function() {
                (function(targetField) {
                    var containerId = targetField.attr("data-save-container-id") || targetField.attr("id");
                    var errorField = $("#" + containerId + "_error");
                    var successField = $("#" + containerId + "_success");
                    var loadingField = $("#" + containerId + "_load");
                    loadingField.closest(".save-loader-wrapper").removeClass("loading");
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
        },
        showError: function(targetField) {
            targetField = targetField || $(targetField);
            var __timeout = this.delayDuration;
            if (!targetField || targetField.length === 0) { return false; }
            setTimeout(function() {
                (function(targetField) {
                    var containerId = targetField.attr("data-save-container-id") || targetField.attr("id");
                    var errorField = $("#" + containerId + "_error");
                    var successField = $("#" + containerId + "_success");
                    var loadingField = $("#" + containerId + "_load");
                    loadingField.closest(".save-loader-wrapper").removeClass("loading");
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
    },
    "getCurrentUser": function(callback, params) {
        callback = callback||function() {};
        if (sessionStorage.currentUser) {
            callback(JSON.parse(sessionStorage.currentUser));
        } else {
            this.sendRequest("/api/me", "GET", "", params, function(data) {
                if (data && data.id) { //make sure the necessary data is there before setting session
                    sessionStorage.setItem("currentUser", JSON.stringify(data));
                }
                callback(data);
            });
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
            if (!data) {
                callback({"error": i18next.t("no data returned")});
                return false;
            }
            if (data.error) {
                callback({"error": i18next.t("unable to get needed core data")});
                return false;
            }
            var ACCEPT_ON_NEXT = "ACCEPT_ON_NEXT"; /* example data format:[{"field": "name"}, {"field": "website_terms_of_use", "collection_method": "ACCEPT_ON_NEXT"}]*/
            var fields = (data.still_needed).map(function(item) {
                return item.field;
            });
            if ($("#topTerms").length > 0) {
                var acceptOnNextCheckboxes = [];
                (data.still_needed).forEach(function(item) {
                    var matchedTermsCheckbox = $("#termsCheckbox [data-type='terms'][data-core-data-type='" + $.trim(item.field) + "']");
                    if (matchedTermsCheckbox.length > 0) {
                        matchedTermsCheckbox.attr({"data-required": "true","data-collection-method": item.collection_method});
                        var parentNode = matchedTermsCheckbox.closest("label.terms-label");
                        if (parentNode.length > 0) {
                            parentNode.show().removeClass("tnth-hide");
                            if (String(item.collection_method).toUpperCase() === ACCEPT_ON_NEXT) {
                                parentNode.find("i").removeClass("fa-square-o").addClass("fa-check-square-o").addClass("edit-view");
                                $("#termsCheckbox, #topTerms .terms-of-use-intro").addClass("tnth-hide");
                                $("#termsText").addClass("agreed");
                                $("#termsCheckbox_default").removeClass("tnth-hide");
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
    "getOptionalCoreData": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User Id is required")});
            return false;
        }
        var __url = "/api/coredata/user/" + userId + "/optional", sessionStorageKey = "optionalCoreData_" + userId;
        if (sessionStorage.getItem(sessionStorageKey)) {
            callback(JSON.parse(sessionStorage.getItem(sessionStorageKey)));
        } else {
            this.sendRequest(__url, "GET", userId, params, function(data) {
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
                    if (containerId) {
                        $("#" + containerId).html(data);
                    }
                    callback(data);
                } else {
                    callback("<div class='error-message'>" + i18next.t("Unable to retrieve portal footer html") + "</div>");
                }
            } else {
                callback("<div class='error-message'>" + i18next.t("No data found") + "</div>");
            }
        });
    },
    "getOrgs": function(userId, params, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/organization", "GET", userId, params, function(data) {
            if (sessionStorage.demoOrgsData) {
                callback(JSON.parse(sessionStorage.demoOrgsData));
                return true;
            }
            if (!data.error) {
                $(".get-orgs-error").html("");
                sessionStorage.setItem("demoOrgsData", JSON.stringify(data));
                callback(data);
            } else {
                var errorMessage = i18next.t("Server error occurred retrieving organization/clinic information.");
                $(".get-orgs-error").html(errorMessage);
                callback({"error": errorMessage});
            }
        });
    },
    "getConsent": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/consent", "GET", userId, params, function(data) {
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
        callback = callback || function() {};
        if (!userId && !params) {
            callback({"error": i18next.t("User id and parameters are required")});
            return false;
        }
        var consented = this.hasConsent(userId, params.org, status);
        var __url = "/api/user/" + userId + "/consent";
        if (consented) {
            callback({error: false});
            return;
        }
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
                if (!data.error) {
                    $(".set-consent-error").html("");
                    callback(data);
                } else {
                    var errorMessage = i18next.t("Server error occurred setting consent status.");
                    callback({"error": errorMessage});
                    $(".set-consent-error").html(errorMessage);
                }
            });
        }
    },
    deleteConsent: function(userId, params) {
        if (!userId || !params) {
            return false;
        }
        var consented = this.getAllValidConsent(userId, params.org);
        if (!consented) {
            return false;
        }
        var arrExcludedOrgIds = params.exclude ? params.exclude.split(","): [];
        var arrConsents = $.grep(consented, function(orgId) {
            var inArray = $.grep(arrExcludedOrgIds, function(eOrg) {
                return String(eOrg) === String(orgId);
            });
           return !(inArray.length); //filter out org Id(s) that are in the array of org Ids to be excluded;
        });
        var self = this;
        arrConsents.forEach(function(orgId) { //delete all consents for the org
            self.sendRequest("/api/user/" + userId + "/consent", "DELETE", userId, {data: JSON.stringify({"organization_id": parseInt(orgId)})}, function(data) {
                if (!data) {
                    return false;
                }
                if (!data.error) {
                    $(".delete-consent-error").html("");
                } else {
                    $(".delete-consent-error").html(i18next.t("Server error occurred removing consent."));
                }
            });
        });
    },
    withdrawConsent: function(userId, orgId, params, callback) {
        callback = callback || function() {};
        if (!userId || !orgId) {
            callback({"error": i18next.t("User id and organization id are required.")});
            return false;
        }
        params = params || {};
        var self = this, arrConsent = [];
        this.sendRequest("/api/user/" + userId + "/consent", "GET", userId, params, function(data) {
            if (data && data.consent_agreements && data.consent_agreements.length > 0) {
                arrConsent = $.grep(data.consent_agreements, function(item) {
                    var expired = item.expires ? tnthDates.getDateDiff(String(item.expires)) : 0; /*global tnthDates */
                    return (String(orgId) === String(item.organization_id)) && !item.deleted && !(expired > 0) && String(item.status) === "suspended";
                });
            }
            if (arrConsent.length > 0) { //don't send request if suspended consent already existed
                return false;
            }
            self.sendRequest("/api/user/" + userId + "/consent/withdraw",
            "POST",
            userId, {sync: params.sync,data: JSON.stringify({organization_id: orgId})},
            function(data) {
                if (data.error) {
                    callback({"error": i18next.t("Error occurred setting suspended consent status.")});
                    return false;
                }
                callback(data);
            });
        });
    },
    getAllValidConsent: function(userId, orgId) {
        if (!userId || !orgId) { return false; }
        var consentedOrgIds = [];
        this.sendRequest("/api/user/" + userId + "/consent", "GET", userId, {sync: true}, function(data) {
            if (!data || data.error || !data.consent_agreements || data.consent_agreements.length === 0) {
                return consentedOrgIds;
            }
            consentedOrgIds = $.grep(data.consent_agreements, function(item) {
                var expired = item.expires ? tnthDates.getDateDiff(String(item.expires)) : 0;
                return !item.deleted && !(expired > 0) && (String(orgId).toLowerCase() === "all" || String(orgId) === String(item.organization_id));
            });
            consentedOrgIds = (consentedOrgIds).map(function(item) {
                return item.organization_id;
            });
            return consentedOrgIds;
        });
        return consentedOrgIds;
    },
    hasConsent: function(userId, orgId, filterStatus) {  /****** NOTE - this will return the latest updated consent entry *******/
        if (!userId || !orgId || String(filterStatus) === "default") { return false; }
        var consentedOrgIds = [], expired = 0, found = false, suspended = false, item = null;
        var __url = "/api/user/" + userId + "/consent", self = this;
        self.sendRequest(__url, "GET", userId, {sync: true}, function(data) {
            if (!data || data.error || (data.consent_agreements && data.consent_agreements.length === 0)) {
                return false;
            }
            consentedOrgIds = $.grep(data.consent_agreements, function(item) {
                var expired = item.expires ? tnthDates.getDateDiff(String(item.expires)) : 0; /*global tnthDates */
                return (String(orgId) === String(item.organization_id)) && !item.deleted && !(expired > 0) && item.staff_editable && item.send_reminders && item.include_in_reports;
            });
        });
        return consentedOrgIds.length;
    },
    "getDemo": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
            return false;
        }
        params = params || {};
        var demoDataKey = "demoData_"+userId;
        if (sessionStorage.getItem(demoDataKey)) {
            callback(JSON.parse(sessionStorage.getItem(demoDataKey)));
            return;
        }
        this.sendRequest("/api/demographics/" + userId, "GET", userId, params, function(data) {
            var errorMessage = "";
            if (data.error) {
                errorMessage = i18next.t("Server error occurred retrieving demographics information.");
                $(".get-demo-error").html(errorMessage);
                callback({"error": errorMessage});
                return false;
            }
            $(".get-demo-error").html(errorMessage);
            sessionStorage.setItem(demoDataKey, JSON.stringify(data));
            callback(data);
        });
    },
    "clearDemoSessionData": function(userId) {
        sessionStorage.removeItem("demoData_"+userId);
    },
    "putDemo": function(userId, toSend, targetField, sync, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User Id is required")});
            return false;
        }
        this.clearDemoSessionData(userId);
        this.sendRequest("/api/demographics/" + userId, "PUT", userId, {sync: sync, data: JSON.stringify(toSend),targetField: targetField}, function(data) {
            if (!data.error) {
                $(".put-demo-error").html("");
            } else {
                $(".put-demo-error").html(i18next.t("Server error occurred setting demographics information."));
            }
            callback(data);
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
        if (!data || !data.entry || data.entry.length === 0) {
            return false;
        }
        var sortedArray = data.entry.sort(function(a, b) { // sort from newest to oldest based on lsat updated date
            return new Date(b.resource.meta.lastUpdated) - new Date(a.resource.meta.lastUpdated);
        });
        var found = false;
        sortedArray.forEach(function(item) {
            if (found) { return true; }
            var resourceItemCode = String(item.resource.code.coding[0].code);
            var system = String(item.resource.code.coding[0].system);
            var procId = item.resource.id;
            if ((resourceItemCode === SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE && (system === SYSTEM_IDENTIFIER_ENUM.SNOMED_SYS_URL)) || (resourceItemCode === SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE && (system === SYSTEM_IDENTIFIER_ENUM.CLINICAL_SYS_URL))) {
                found = {"code": resourceItemCode,"id": procId};
            }
        });
        return found;
    },
    "getTreatment": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required")});
            return false;
        }
        this.sendRequest("/api/patient/" + userId + "/procedure", "GET", userId, params, function(data) {
            if (data.error) {
                $("#userProcedures").html("<span class='error-message'>" + i18next.t("Error retrieving data from server") + "</span>");
            }
            callback(data);
        });
    },
    "postTreatment": function(userId, started, treatmentDate, targetField) {
        if (!userId) { return false;}
        tnthAjax.deleteTreatment(userId, targetField);
        var code = SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE, display = "None", system = SYSTEM_IDENTIFIER_ENUM.CLINICAL_SYS_URL;
        if (started) {
            code = SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE;
            display = "Procedure on prostate";
            system = SYSTEM_IDENTIFIER_ENUM.SNOMED_SYS_URL;
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
        this.sendRequest("/api/patient/" + userId + "/procedure", "GET", userId, {sync: true}, function(data) {
            if (!data || data.error) { return false; }
            var treatmentData = tnthAjax.hasTreatment(data);
            if (!treatmentData) { return false; }
            if (String(treatmentData.code) === String(SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE)){
                tnthAjax.deleteProc(treatmentData.id, targetField, true);
                return true;
            }
            tnthAjax.deleteProc(treatmentData.id, targetField, true);
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
            if (!data) {
                callback({"error": i18next.t("no data returned")});
                return false;
            }
            if (data.error) {
                var errorMessage = i18next.t("Server error occurred saving procedure/treatment information.");
                $("#userProcuedures .get-procs-error").html(errorMessage);
                callback({error: errorMessage});
                return false;
            }
            $(".get-procs-error").html("");
            callback(data);
        });
    },
    "deleteProc": function(procedureId, targetField, sync) {
        this.sendRequest("/api/procedure/" + procedureId, "DELETE", null, {sync: sync,targetField: targetField}, function(data) {
            if (!data.error) {
                $(".del-procs-error").html("");
            } else {
                $(".del-procs-error").html(i18next.t("Server error occurred removing procedure/treatment information."));
            }
        });
    },
    "getRoleList": function(params, callback) {
        this.sendRequest("/api/roles", "GET", null, params, function(data) {
            callback = callback || function() {};
            if (!data.error) {
                callback(data);
            } else {
                var errorMessage = i18next.t("Server error occurred retrieving roles information.");
                $(".get-roles-error").html(errorMessage);
                callback({"error": errorMessage});
            }
        });
    },
    "getRoles": function(userId, callback, params) {
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
    "removeCachedRoles": function(userId) {
        sessionStorage.removeItem("userRole_"+userId);
    },
    "putRoles": function(userId, toSend, targetField, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User Id is required.")});
            return false;
        }
        this.removeCachedRoles(userId);
        this.sendRequest("/api/user/" + userId + "/roles", "PUT", userId, {data: JSON.stringify(toSend),targetField: targetField}, function(data) {
            if (!data || data.error) {
                var errorMessage = i18next.t("Server error occurred setting user role information.");
                $(".put-roles-error").html(errorMessage);
                callback({error: errorMessage});
                return;
            }
            $(".put-roles-error").html("");
            sessionStorage.setItem("userRole_" + userId, "");
            callback(data);
        });
    },
    "deleteRoles": function(userId, toSend) {
        if (!userId) {
            return false;
        }
        this.removeCachedRoles(userId);
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
    "getClinical": function(userId, params, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/patient/" + userId + "/clinical", "GET", userId, params, function(data) {
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
    "getObservationId": function(userId, code) {
        if (!userId) { return false; }
        var obId = "",_code = "";
        this.sendRequest("/api/patient/" + userId + "/clinical", "GET", userId, {sync: true}, function(data) {
            if (data) {
                if (!data.error) {
                    if (data.entry) {
                        (data.entry).forEach(function(item) {
                            if (!obId) {
                                _code = item.content.code.coding[0].code;
                                if (String(_code) === String(code)) {
                                    obId = item.content.id;
                                }
                            }
                        });
                    }
                }
            }
        });
        return obId;
    },
    "postClinical": function(userId, toCall, toSend, status, targetField, params, callback) {
        if (!userId) { return false; }
        params = params || {};
        var code = "", display = "";
        if (CLINICAL_CODE_ENUM.hasOwnProperty(String(toCall).toLowerCase())) {
            var match = CLINICAL_CODE_ENUM[toCall];
            code = match.code;
            display = match.display;
        }
        if (!code) {
            return false;
        }
        var system = SYSTEM_IDENTIFIER_ENUM.CLINICAL_SYS_URL;
        var method = "POST";
        var url = "/api/patient/" + userId + "/clinical";
        var obsCode = [{"code": code,"display": display,"system": system}];
        var obsArray = {};
        obsArray.resourceType = "Observation";
        obsArray.code = {"coding": obsCode};
        obsArray.issued = params.issuedDate ? params.issuedDate : "";
        obsArray.status = status ? status : "";
        obsArray.valueQuantity = {"units": "boolean","value": toSend};
        if (params.performer) {
            obsArray.performer = params.performer;
        }
        var obsId = tnthAjax.getObservationId(userId, code);
        if (obsId) {
            method = "PUT";
            url = url + "/" + obsId;
        }
        callback = callback || function() {};
        this.sendRequest(url, method, userId, {data: JSON.stringify(obsArray),targetField: targetField}, function(data) {
            if (!data || data.error) {
                var errorMessage = i18next.t("Server error occurred updating clinical data.");
                $(".post-clinical-error").html(errorMessage).show();
                callback({error: errorMessage});
                return;
            }
            $(".post-clinical-error").html("").hide();
            callback(data);
        });
    },
    "getTermsUrl": function(sync, callback) { /*global i18next */
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
                                    if (!qList[orgID]) {
                                        qList[orgID] = []; //don't assign orgID to object if it was already present
                                    }
                                    if (item.questionnaires) {
                                        (item.questionnaires).forEach(function(q) {
                                            /*
                                             * add instrument name to instruments array for the org - will not add if it is already in the array
                                             * NOTE: inArray returns -1 if the item is NOT in the array
                                             */
                                            if ($.inArray(q.questionnaire.display, qList[orgID]) === -1) {
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
        params = params || {};
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
        this.sendRequest("/api/user/" + userId + "/tou/accepted", "POST", userId, {data: JSON.stringify(toSend)}, function(data) {
            if (data) {
                if (!data.error) {
                    $(".post-tou-error").html("");
                } else {
                    $(".post-tou-error").html(i18next.t("Server error occurred saving terms of use information."));
                }
            }
        });
    },
    "postTerms": function(toSend, targetField, callback) {
        callback = callback || function() {};
        this.sendRequest("/api/tou/accepted", "POST", null, {data: JSON.stringify(toSend), targetField: targetField}, function(data) {
            if (!data || data.error) {
                var errorMessage = i18next.t("Server error occurred saving terms of use information.");
                $(".post-tou-error").html(errorMessage);
                callback({error: errorMessage});
                return;
            }
            $(".post-tou-error").html("");
            callback(data);
        });
    },
    "accessUrl": function(userId, sync, callback) {
        callback = callback || function() {};
        if (!userId) { callback({"error": i18next.t("User id is required.")}); return false; }
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
        if (!data) { callback({"error": i18next.t("Invite data are required.")}); return false; }
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
        if (!userId) { callback({"error": i18next.t("User id is required.")}); return false; }
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
        if (!userId) { callback({"error": i18next.t("User id is required.")}); return false; }
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
        if (!userId) { callback({"error": i18next.t("User id is required.")}); return false; }
        if (!data) { callback({"error": i18next.t("Questionnaire response data is required.")}); return false;}
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
    "assessmentList": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/patient/" + userId + "/assessment", "GET", userId, params, function(data) {
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
    "patientReport": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/user_documents?document_type=PatientReport", "GET", userId, params, function(data) {
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
        params = params || {};
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
        params = params || {};
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
    "emailLog": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/messages", "GET", userId, params, function(data) {
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
    "auditLog": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/audit", "GET", userId, params, function(data) {
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
        params = params || {};
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
    "deactivateUser": function(userId, params, callback) {
        callback = callback||function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required")});
            return false;
        }
        this.sendRequest("/api/user/" + userId, "DELETE", userId, (params || {}), function(data) {
            callback = callback||function() {};
            if (!data || data.error) {
                callback({"error": i18next.t("Error occurred deactivating user.")});
                return;
            }
            callback(data);
        });
    },
    "reactivateUser": function(userId, params, callback) {
        callback = callback||function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/reactivate", "POST", userId, (params || {}), function(data) {
            if (!data || data.error) {
                callback({"error": i18next.t("Error occurred reactivating user.")});
                return;
            }
            callback(data);
        });
    },
    "setConfigurationUI": function(configKey, value) {
        if (!configKey || $("#profile_" + configKey).length > 0) { return false; }
        $("body").append("<input type='hidden' id='profile_" + configKey + "' value='" + (value ? value : "") + "'/>");
    },
    "getConfigurationByKey": function(configVar, userId, params, callback, setConfigInUI) {
        callback = callback || function() {};
        var self = this;
        if (!userId) {
            callback({"error": i18next.t("User id is required.")});
            return false;
        }
        if (!configVar) {
            callback({"error": i18next.t("configuration variable name is required.")});
            return false;
        }
        var sessionConfigKey = "config_" + configVar + "_" + userId;
        if (sessionStorage.getItem(sessionConfigKey)) {
            var data = JSON.parse(sessionStorage.getItem(sessionConfigKey));
            if (setConfigInUI) { self.setConfigurationUI(configVar, data[configVar] + "");}
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
                    callback({"error": i18next.t("no data returned")});
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
    },
    "getEmailReady": function(userId, params, callback) {
        callback = callback || function() {};
        if (!userId) {
            callback({error: i18next.t("User id is required.")});
            return false;
        }
        this.sendRequest("/api/user/" + userId + "/email_ready", "GET", userId, params, function(data) {
            callback(data);
        });
    }
};

var tnthDates = {
    /** validateDateInputFields  check whether the date is a sensible date in month, day and year fields.
     ** params: month, day and year fields and error field ID
     ** NOTE this can replace the custom validation check; hook this up to the onchange/blur event of birthday field
     ** work better in conjunction with HTML5 native validation check on the field e.g. required, pattern match  ***/
    "validateDateInputFields": function(monthField, dayField, yearField, errorFieldId) {
        var m = $(monthField).val(), d = $(dayField).val(), y = $(yearField).val();
        if (m && d && y) {
            if ($(yearField).get(0).validity.valid && $(monthField).get(0).validity.valid && $(dayField).get(0).validity.valid) {
                m = parseInt(m);
                d = parseInt(d);
                y = parseInt(y);
                var errorField = $("#" + errorFieldId);

                if (!(isNaN(m)) && !(isNaN(d)) && !(isNaN(y))) {
                    var today = new Date();
                    var date = new Date(y, m - 1, d);
                    if (!(date.getFullYear() === y && (date.getMonth() + 1) === m && date.getDate() === d)) { // Check to see if this is a real date
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
                } else {
                    return false;
                }
            } else {
                return false;
            }
        } else {
            return false;
        }
    },
    /**
     * Simply swaps: a/b/cdef to b/a/cdef (single & double digit permutations accepted...)
     * Does not check for valid dates on input or output!
     * @param currentDate string eg 7/4/1976
     * @returns string eg 4/7/1976
     */
    "swap_mm_dd": function(currentDate) {
        var splitDate = currentDate.split("/");
        return splitDate[1] + "/" + splitDate[0] + "/" + splitDate[2];
    },
    "convertMonthNumeric": function(month) { //Convert month string to numeric
        if (!month) { return ""; }
        else {
            var month_map = {"jan": 1,"feb": 2,"mar": 3,"apr": 4,"may": 5,"jun": 6,"jul": 7,"aug": 8,"sep": 9,"oct": 10,"nov": 11,"dec": 12};
            var m = month_map[month.toLowerCase()];
            return m ? m : "";
        }
    },
    "convertMonthString": function(month) { //Convert month string to text
        if (!month) {
            return "";
        } else {
            var numeric_month_map = {1: "Jan",2: "Feb",3: "Mar",4: "Apr",5: "May",6: "Jun",7: "Jul",8: "Aug",9: "Sep",10: "Oct",11: "Nov",12: "Dec"};
            var m = numeric_month_map[parseInt(month)];
            return m ? m : "";
        }
    },
    "isDate": function(obj) {
        return Object.prototype.toString.call(obj) === "[object Date]" && !isNaN(obj.getTime());
    },
    "displayDateString": function(m, d, y) {
        var s = "";
        s += (d ? d : "");
        if (m) {
            s += (s ? " " : "") + this.convertMonthString(m);
        }
        if (y) {
            s += (s ? " " : "") + y;
        }
        return s;
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
        } else { // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime();
        }
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24)); // Round down to floor so we don't add an extra day if session is 12+ hours into the day
    },
    "isValidDefaultDateFormat": function(date, errorField) {
        if (!date || date.length < 10) { return false; }
        var dArray = $.trim(date).split(" ");
        if (dArray.length < 3) { return false; }
        var day = parseInt(dArray[0])+"", month = dArray[1], year = dArray[2];
        if (day.length < 1 || month.length < 3 || year.length < 4) { return false; }
        if (!/(0)?[1-9]|1\d|2\d|3[01]/.test(day)) { return false; }
        if (!/jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/i.test(month)) { return false; }
        if (!/(19|20)\d{2}/.test(year)) { return false; }
        var dt = new Date(date);
        if (!this.isDateObj(dt)) { return false; }
        else if (!this.isValidDate(year, this.convertMonthNumeric(month), day)) {
            return false;
        } else {
            var today = new Date(),
                errorMsg = "";
            if (dt.getFullYear() < 1900) { errorMsg = "Year must be after 1900"; }
            // Only allow if date is before today
            if (dt.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                errorMsg = "The date must not be in the future.";
            }
            if (errorMsg) {
                $(errorField).text(errorMsg);
                return false;
            } else {
                $(errorField).text("");
                return true;
            }
        }
    },
    "isDateObj": function(d) {
        return Object.prototype.toString.call(d) === "[object Date]" && !isNaN(d.getTime());
    },
    "isValidDate": function(y, m, d) {
        var date = this.getDateObj(y, m, d), convertedDate = this.getConvertedDate(date), givenDate = this.getGivenDate(y, m, d);
        return String(givenDate) === String(convertedDate);
    },
    /*
     * method does not check for valid numbers, will return NaN if conversion failed
     */
    "getDateObj": function(y, m, d, h, mi, s) {
        h = h || 0;
        mi = mi || 0;
        s = s || 0;
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d), parseInt(h), parseInt(mi), parseInt(s));
    },
    "getConvertedDate": function(dateObj) {
        if (dateObj && this.isDateObj(dateObj)) { return "" + dateObj.getFullYear() + (dateObj.getMonth() + 1) + dateObj.getDate(); }
        else { return ""; }
    },
    "getGivenDate": function(y, m, d) {
        return "" + y + m + d;
    },
    "formatDateString": function(dateString, format) { //NB For dateString in ISO-8601 format date as returned from server e.g. '2011-06-29T16:52:48'
        if (dateString) {
            var iosDateTest = /^([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3([12]\d|0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-9]|0[1-9]\d|[12]\d{2}|3([0-5]\d|6[1-6])))([T\s]((([01]\d|2[0-3])((:?)[0-5]\d)?|24\:?00)([\.,]\d+(?!:))?)?(\17[0-5]\d([\.,]\d+)?)?([zZ]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?)?)?$/;
            var d = new Date(dateString);
            var day, month, year, hours, minutes, seconds, nd;
            if (!iosDateTest && !isNaN(d) && !this.isDateObj(d)) { //note instantiating ios formatted date using Date object resulted in error in IE
                return "";
            }
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
        } else {
            return "";
        }
    },
    "convertToLocalTime": function(dateString) {
        var convertedDate = "";
        if (dateString) { //assuming dateString is UTC date/time
            var d = new Date(dateString);
            var newDate = new Date(d.getTime() + d.getTimezoneOffset() * 60 * 1000);
            var offset = d.getTimezoneOffset() / 60;
            var hours = d.getHours();
            newDate.setHours(hours - offset);
            var options = {year: "numeric", day: "numeric", month: "short", hour: "numeric", minute: "numeric", second: "numeric", hour12: false};
            convertedDate = newDate.toLocaleString(options);
        }
        return convertedDate;
    },
    "getUserTimeZone": function(userId) {
        var selectVal = $("#profileTimeZone").length > 0 ? $("#profileTimeZone option:selected").val() : "", userTimeZone = "UTC";
        if (String(selectVal) !== "") {
            userTimeZone = selectVal;
        } else {
            if (!userId) {
                return userTimeZone;
            }
            tnthAjax.sendRequest("/api/demographics/" + userId, "GET", userId, {
                sync: true
            }, function(data) {
                if (!data.error && data.extension) {
                    data.extension.forEach(
                        function(item) {
                            if (item.url === SYSTEM_IDENTIFIER_ENUM.timezone) {
                                userTimeZone = item.timezone;
                            }
                        });
                }
            });
        }
        return userTimeZone;
    },
    "localeSessionKey": "currentUserLocale",
    "clearSessionLocale": function() {
        sessionStorage.removeItem(this.localeSessionKey);
    },
    "getUserLocale": function() {
        var sessionKey = this.localeSessionKey;
        var sessionLocale = sessionStorage.getItem(sessionKey);
        var locale = "";
        if (sessionLocale) {
            return sessionLocale;
        }
        if (!checkJQuery()) { /*global checkJQuery */
            return false;
        }
        var userSessionLocale = $("#userSessionLocale").val();
        if (userSessionLocale) {
            sessionStorage.setItem(sessionKey, userSessionLocale);
            return userSessionLocale;
        }
        $.ajax({
            type: "GET",
            url: "/api/me",
            async: false
        }).done(function(data) {
            var userId = "";
            if (data) { userId = data.id; }
            if (!userId) {
                locale = "en_us";
                return false;
            }
            $.ajax({
                type: "GET",
                url: "/api/demographics/" + userId, //dont use tnthAjax method - don't want to report error here if failed
                async: false
            }).done(function(data) {
                if (!data || !data.communication) {
                    locale = "en_us";
                    return false;
                }
                data.communication.forEach(function(item) {
                    if (item.language) {
                        locale = item.language.coding[0].code;
                        sessionStorage.setItem(sessionKey, locale);
                    }
                });
            });
        }).fail(function() {});
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
        return tnthDates.formatDateString(utcDate, "yyyy-mm-dd hh:mm:ss");  //I believe this is a valid python date format, will save it as GMT date/time NOTE, conversion already occurred, so there will be no need for backend to convert it again
    },
    getTodayDateObj: function() { //return object containing today's date/time information
        var today = new Date();
        var td = today.getDate(), tm = today.getMonth() + 1, ty = today.getFullYear();
        var th = today.getHours(), tmi = today.getMinutes(), ts = today.getSeconds();
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
    dateValidator: function(day, month, year, restrictToPresent) { //parameters: day, month and year values in numeric, boolean value for restrictToPresent, true if the date needs to be before today, false is the default
        var errorMessage = "";
        if (day && month && year) {
            var iy = parseInt(year), im = parseInt(month), iid = parseInt(day), date = new Date(iy, im - 1, iid);
            if (date.getFullYear() === iy && (date.getMonth() + 1) === im && date.getDate() === iid) { // Check to see if this is a real date
                if (iy < 1900) {
                    errorMessage = i18next.t("Year must be after 1900");
                }
                if (restrictToPresent) { // Only allow if date is before today
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
/*global tnthAjax OrgTool tnthDates SYSTEM_IDENTIFIER_ENUM embed_page $ */
/*global i18next */
var Global = {
    "registerModules": function() { //TODO use webpack or requireJS to import modules?
        if (!window.portalModules) {
            window.portalModules = {};
        }
        window.portalModules.SYSTEM_IDENTIFIER_ENUM = SYSTEM_IDENTIFIER_ENUM;
        window.portalModules.tnthAjax = tnthAjax;
        window.portalModules.tnthDates = tnthDates;
        window.portalModules.orgTool = OrgTool;
        if (typeof i18next !== "undefined") {
            window.portalModules.i18next = i18next;
        }
    },
    "initPortalWrapper": function(PORTAL_NAV_PAGE, callback) {
        callback = callback || function() {};
        var self = this;
        sendRequest(PORTAL_NAV_PAGE, {cache: false}, function(data) { /*global sendRequest */
            if (!data || data.error) {
                tnthAjax.reportError("", PORTAL_NAV_PAGE, data.error || i18next.t("Error loading portal wrapper"), true);
                $("#mainNavLoadingError").html(i18next.t("Error loading portal wrapper"))
                restoreVis(); /*global restoreVis */
                callback();
                return false;
            }
            embed_page(data);
            setTimeout(function() {
                $("#tnthNavWrapper .logout").on("click", function(event) {
                    event.stopImmediatePropagation();
                    sessionStorage.clear();
                });
            }, 150);
            self.getNotification(function(data) { //ajax to get notifications information
                self.notifications(data);
            });
            callback();
        });
    },
    "loginAs": function() {
        var LOGIN_AS_PATIENT = (typeof sessionStorage !== "undefined") ? sessionStorage.getItem("loginAsPatient") : null;
        if (LOGIN_AS_PATIENT) {
            tnthDates.clearSessionLocale();
            tnthDates.getUserLocale(); /*global tnthDates */ //need to clear current user locale in session storage when logging in as patient
            var historyDefined = typeof history !== "undefined" && history.pushState;
            if (historyDefined) {
                history.pushState(null, null, location.href);
            }
            window.addEventListener("popstate", function() {
                if (historyDefined) {
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
            var userLocale = tnthDates.getUserLocale(), footerElements = $("#homeFooter .copyright");
            var getContent = function(cc) {
                var content = "";
                switch (String(cc.toUpperCase())) {
                case "EN_US":
                    content = i18next.t("&copy; 2017 Movember Foundation. All rights reserved. A registered 501(c)3 non-profit organization (Movember Foundation).");
                    break;
                case "EN_AU":
                    content = i18next.t("&copy; 2017 Movember Foundation. All rights reserved. Movember Foundation is a registered charity in Australia ABN 48894537905 (Movember Foundation).");
                    break;
                case "EN_NZ":
                    content = i18next.t("&copy; 2017 Movember Foundation. All rights reserved. Movember Foundation is a New Zealand registered charity number CC51320 (Movember Foundation).");
                    break;
                default:
                    content = i18next.t("&copy; 2017 Movember Foundation (Movember Foundation). All rights reserved.");

                }
                return content;

            };
            footerElements.html(getContent(userLocale));
        }, 500);
    },
    "getNotification": function(callback) {
        callback = callback || function() {};
        var userId = $("#notificationUserId").val();
        if (!userId) {
            callback({"error": i18next.t("User id is required")});
            return false;
        }
        $.ajax({
            type:"GET",
            url: "/api/user/"+userId+"/notification"
        }).done(function(data) {
            if (data) {
                callback(data);
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        }).fail(function(){
            callback({"error": i18next.t("Error occurred retrieving notification.")});
        });
    },
    "deleteNotification": function(userId, notificationId) {
        if (!userId || parseInt(notificationId) < 0 || !notificationId) {
            return false;
        }
        var self = this;
        this.getNotification(function(data) {
            if (data.notifications && data.notifications.length > 0) {
                var arrNotification = $.grep(data.notifications, function(notification) { //check if there is notification for this id -dealing with use case where user deletes same notification in a separate open window
                    return parseInt(notification.id) === parseInt(notificationId);
                });
                var userId = $("#notificationUserId").val();
                if (arrNotification.length > 0 && userId) { //delete notification only if it exists
                    $.ajax({
                        type: "DELETE",
                        url: "/api/user/" + userId + "/notification/" + notificationId
                    }).done(function() {
                        $("#notification_" + notificationId).attr("data-visited", true);
                        $("#notification_" + notificationId).find("[data-action-required]").removeAttr("data-action-required");
                        self.setNotificationsDisplay();
                    });
                }
            }
        });
    },
    "notifications": function(data) {
        if (!data || !data.notifications || data.notifications.length === 0) {
            $("#notificationBanner").hide();
            return false;
        }
        var arrNotificationText = (data.notifications).map(function(notice) {
            return "<div class='notification' id='notification_{notificationId}' data-id='{notificationId}' data-name='{notificationName}'>{notificationContent}</div>"
                .replace(/\{notificationId\}/g, notice.id)
                .replace(/\{notificationName\}/g, notice.name)
                .replace(/\{notificationContent\}/g, notice.content);
        });
        var self = this;
        $("#notificationBanner .content").html(arrNotificationText.join(""));
        $("#notificationBanner .notification").addClass("active");
        $("#notificationBanner").show();
        $("#notificationBanner [data-id] a").each(function() {
            $(this).on("click", function(e) {
                e.stopPropagation();
                var parentElement = $(this).closest(".notification");
                parentElement.attr("data-visited", "true"); //adding the attribute data-visited will hide the notification entry
                self.deleteNotification($("#notificationUserId").val(), parentElement.attr("data-id")); //delete relevant notification
                self.setNotificationsDisplay();
            });
        });
        $("#notificationBanner .close").on("click", function(e) { //closing the banner
            e.stopPropagation();
            $("#notificationBanner [data-id]").each(function() {
                var actionRequired = $(this).find("[data-action-required]").length > 0;
                if (!actionRequired) {
                    $(this).attr("data-visited", true);
                    self.deleteNotification($("#notificationUserId").val(), $(this).attr("data-id"));
                }
            });
            self.setNotificationsDisplay();
        });
        self.setNotificationsDisplay();
    },
    "setNotificationsDisplay": function() {
        if ($("#notificationBanner [data-action-required]").length > 0) { //requiring user action
            $("#notificationBanner .close").removeClass("active");
            return false;
        }
        var allVisited = true;
        $("#notificationBanner [data-id]").each(function() {
            if (allVisited && !$(this).attr("data-visited")) { //check if all links have been visited
                allVisited = false;
                return false;
            }
        });
        if (allVisited) {
            $("#notificationBanner").hide();
        } else {
            $("#notificationBanner .close").addClass("active");
        }
    },
    initValidator: function() {
        if (typeof $.fn.validator === "undefined") { return false; }
        $("form.to-validate").validator({ // To validate a form, add class to <form> and validate by ID.
            custom: {
                birthday: function() {
                    var m = parseInt($("#month").val()), d = parseInt($("#date").val()), y = parseInt($("#year").val());
                    var goodDate = true, errorMsg = "";
                    // If NaN then the values haven't been entered yet, so we, validate as true until other fields are entered
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
                            $el.trigger("postEventUpdate");
                        }
                    };
                    if (emailVal === "") {
                        if (!$el.attr("data-optional")) {
                            return false;
                        }
                        update($el); //if email address is optional, update it as is
                        return true;
                    }
                    var emailReg = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                    var addUserId = ""; // Add user_id to api call (used on patient_profile page so that staff can edit)
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
                    if (invalid) { $("#error" + $el.attr("id")).html("Invalid characters in text."); }
                    else {$("#error" + $el.attr("id")).html("");}
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
    }
};

var userSetLang = tnthDates.getUserLocale();
/*global __i18next*/
Global.registerModules();
__i18next.init({"lng": userSetLang
}, function() {
    if (!checkJQuery()) { alert("JQuery library necessary for this website was not loaded.  Please refresh your browser and try again."); return false; }
    if (typeof i18next === "undefined") { i18next = {t: function(key) { return key; }}; } //fallback for i18next in older browser?
    $(document).ready(function() {
        var PORTAL_NAV_PAGE = window.location.protocol + "//" + window.location.host + "/api/portal-wrapper-html/";
        if (PORTAL_NAV_PAGE) {
            loader(true); /*global loader restoreVis*/
            try {
                Global.initPortalWrapper(PORTAL_NAV_PAGE);
            } catch(e) {
                tnthAjax.reportError("", PORTAL_NAV_PAGE, i18next.t("Error loading portal wrapper"), true);
                restoreVis();
            }
        } else { restoreVis();  }
        if ($("#alertModal").length > 0) {  $("#alertModal").modal("show");}
        tnthAjax.beforeSend();
        Global.footer();
        Global.loginAs();
        Global.initValidator();
    });
});
