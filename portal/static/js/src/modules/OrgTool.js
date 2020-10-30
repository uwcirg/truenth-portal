import SYSTEM_IDENTIFIER_ENUM from "./SYSTEM_IDENTIFIER_ENUM.js";
import tnthAjax from "./TnthAjax.js";
import Consent from "./Consent.js";
import {EPROMS_SUBSTUDY_ID} from "../data/common/consts.js";

export default (function() { /*global i18next $ */
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
        this.containerElementId = "fillOrgs";
        this.TOP_LEVEL_ORGS = [];
        this.orgsList = {};
        this.orgsData = [];
        this.initialized = false;
    };

    OrgTool.prototype.init = function(callback, orgsElementsContainerId) {
        var self = this;
        callback = callback || function() {};
        this.setContainerElementId(orgsElementsContainerId);
        if (sessionStorage.orgsData) {
            var orgsData = JSON.parse(sessionStorage.orgsData);
            self.orgsData = orgsData;
            self.populateOrgsList(orgsData);
            callback(orgsData);
        } else {
            $.ajax({
                type: "GET",
                url: "/api/organization",
                async: false
            }).done(function(data) {
                if (data && data.entry) {
                    self.orgsData = data.entry;
                    self.populateOrgsList(data.entry);
                    sessionStorage.setItem("orgsData", JSON.stringify(data.entry));
                    callback(data.entry);
                }
            }).fail(function(xhr) {
                callback({"error": xhr.responseText});
                //logging error
                tnthAjax.reportError("n/a", "/api/organization", "Error occurred initializing UI organizations " + (xhr && xhr.responseText  ? xhr.responseText : "Server response not available"));
            });
        }
    };
    OrgTool.prototype.setContainerElementId = function(id) {
        if (id) {
            this.containerElementId = id;
        }
    };
    OrgTool.prototype.getContainerElementId = function() {
        return this.containerElementId;
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
        $("#" + this.containerElementId).attr("userId", userId);
    };
    OrgTool.prototype.getUserId = function() {
        return $("#" + this.containerElementId).attr("userId");
    };
    OrgTool.prototype.inArray = function(n, array){
        if (!n || !array || !Array.isArray(array)) { return false; }
        var found = false;
        for (var index = 0; !found && index < array.length; index++) {
            found = String(array[index]) === String(n);
        }
        return found;
    };
    OrgTool.prototype.getElementParentOrg = function(o){
        var parentOrg;
        if (!o) {
            return false;
        }
        parentOrg = $(o).attr("data-parent-id");
        if (!parentOrg) {
            parentOrg = $(o).closest(".org-container[data-parent-id]").attr("data-parent-id");
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
    OrgTool.prototype.getOrgsList = function(){
        if (!Object.keys(this.orgsList).length) {
            this.init();
            return this.orgsList;
        }
        return this.orgsList;
    };
    OrgTool.prototype.getOrgName = function(orgId){
        var orgsList = this.getOrgsList();
        if (orgId && orgsList.hasOwnProperty(orgId)) {
            return orgsList[orgId].name;
        }
        return "";
    };
    OrgTool.prototype.getResearchProtocolsByOrgId = function(orgId) {
        var orgsList = this.getOrgsList();
        if (!orgId || !orgsList.hasOwnProperty(orgId) || !orgsList[orgId].extension) return [];
        let researchProtocols =  orgsList[orgId].extension.filter(ex => {
            return ex.research_protocols;
        });
        if (!researchProtocols.length) return [];
        return researchProtocols[0].research_protocols;
    }
    OrgTool.prototype.isSubStudyOrg = function(orgId, params) {
        if (!orgId) return false;
        params = params || {};
        var orgsList = this.getOrgsList();
        if (!orgsList.hasOwnProperty(orgId)) return false;
        if (!this.getResearchProtocolsByOrgId(orgId).length) {
            if (sessionStorage.getItem(`extension_${orgId}`)) {
                orgsList[orgId].extension = [...JSON.parse(sessionStorage.getItem(`extension_${orgId}`))];
            } else {
                /*
                * include flag for inherited attributes to find added inherited attributes that include research study
                * information
                */
                tnthAjax.getOrg(orgId, {include_inherited_attributes: true, sync: params.async ? false : true}, function(data) {
                    if (data && data.extension) {
                        orgsList[orgId].extension = [...data.extension];
                        sessionStorage.setItem(`extension_${orgId}`, JSON.stringify(data.extension));
                    }
                });
            }
        }
        let researchProtocolSet = this.getResearchProtocolsByOrgId(orgId);

        /*
         * match substudy research protocol study id with that from the org
         */
        return researchProtocolSet.filter(p => {
            return parseInt(p.research_study_id) === EPROMS_SUBSTUDY_ID;
        }).length > 0;
    };
    OrgTool.prototype.filterOrgs = function(leafOrgs) {
        leafOrgs = leafOrgs || [];
        if (leafOrgs.length === 0) { return false; }
        var self = this;
        $("#" + this.containerElementId + " input[name='organization']").each(function() {
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
            $("#" + self.containerElementId + " .org-container[data-parent-id='" + orgId + "']").each(function() {
                var subOrgs = $(this).find(".org-container");
                if (subOrgs.length > 0) {
                    var allSubOrgsHidden = true;
                    subOrgs.each(function() {
                        var visibleInputElements = $.grep($(this).find("input[name='organization']"), function(el){
                            return $(el).is(":visible") || String($(el).css("display")) !== "none";
                        });
                        if (!visibleInputElements.length) {
                            $(this).hide();
                        } else {
                            //set flag to false and return, no need to continue;
                            allSubOrgsHidden = false;
                            return false;
                        }
                    });
                    if (allSubOrgsHidden) {
                        $(this).children("label").hide();
                    }
                } 
            });
            /* for each top level organization, if there is matching org elements, show the legend, else hide it*/
            var parentContainer = $("#" + orgId + "_container");
            var inputElements = parentContainer.find("input[name='organization']");
            var eligibleEls = $.grep (inputElements, function(el) {
                return $(el).is(":visible") || String($(el).css("display")) !== "none";
            });
            if (eligibleEls.length) {
                parentContainer.find("legend").show();
            } else {
                parentContainer.find("legend").hide()
            }
        });

    };
    OrgTool.prototype.findOrg = function(entry, orgId){
        var org;
        if (!entry || !orgId) {
            return false;
        }
        entry.forEach(function(item) {
            if (!org) {
                if (parseInt(item.id) === parseInt(orgId)) {
                    org = item;
                }
            }
        });
        return org;
    };
    OrgTool.prototype.getOrgName = function(orgId){
        var org = this.orgsList[orgId];
        if (!org) {
            return "";
        }
        return org.name;
    };
    /*
     * return the immediate parent organization ID for a given organization Id
     */
    OrgTool.prototype.getParentOrgId = function(orgId){
        var org = this.orgsList[orgId];
        if (!org) {
            return "";
        }
        return org.parentOrgId;
    };
    /*
     * return the UI element associated with an organization ID
     */
    OrgTool.prototype.getElementByOrgId = function(orgId) {
        return $("#userOrgs input[name='organization'][value='" + orgId + "']");
    };
    OrgTool.prototype.populateOrgsList = function(items) {
        if (Object.keys(this.orgsList).length > 0) {
            return this.orgsList;
        }
        var entry = items, self = this, parentId, orgsList = {};
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
        return orgsList;
    };
    OrgTool.prototype.populateUI = function(){
        let container = $("#"+this.getContainerElementId());
        if (!container.length) {
            return;
        }
        if (sessionStorage.orgsHTML) {
            $("#" + this.getContainerElementId()).html(sessionStorage.orgsHTML);
            return true;
        }
        var self = this, orgsList = this.orgsList, parentContent = "";
        var getState = (item) => {
            if (!item.identifier) {
                return "";
            }
            var s = "", found = false;
            (item.identifier).forEach(function(i) {
                if (!found && (i.system === SYSTEM_IDENTIFIER_ENUM.practice_region && i.value)) {
                    s = (i.value).split(":")[1];
                    found = true;
                }
            });
            return s;
        };
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
            let parentOrgItem = orgsList[org];
            let orgShortName = parentOrgItem.shortname || parentOrgItem.name;
            let parentState = getState(parentOrgItem);
            let parentOrgName = parentOrgItem.name;
            if (parentOrgItem.children.length) {
                if ($("#userOrgs legend[orgId='" + org + "']").length === 0) {
                    parentDiv.classList.add("parent-org-container");
                    parentContent = `<legend orgId="${org}">${parentOrgName}</legend>
                        <input class="tnth-hide" type="checkbox" name="organization" parent_org="true" data-org-name="${parentOrgName}" data-short-name="${orgShortName}" id="${org}_org" state="${parentState}" value="${org}" /></div>`;
                }
            } else {
                if ($("#userOrgs label[id='org-label-" + org + "']").length === 0) {
                    parentDiv.classList.add("parent-org-container", "parent-singleton");
                    parentContent = `
                        <legend orgId="${org}" class="singleton">${parentOrgName}</legend>
                        <label id="org-label-${org}" class="org-label text-muted">
                        <input class="clinic" type="checkbox" name="organization" parent_org="true" id="${org}_org" state="${parentState}" value="${org}"
                        data-parent-id="${org}"  data-org-name="${parentOrgName}" data-short-name="${orgShortName}" data-parent-name="${parentOrgName}"/>${parentOrgName}</label></div>`;
                }
            }
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

                    if ($("#" + self.getContainerElementId() + " input[name='organization'][value='" + item.id + "']").length > 0) {
                        return true;
                    }
                    var attrObj = {dataAttributes:(' data-parent-id="' + topLevelOrgId + '"  data-parent-name="' + orgsList[topLevelOrgId].name + '" '), containerClass: "", textClass: ""};
                    if (_isTopLevel) {
                        attrObj.containerClass = "sub-org-container";
                        attrObj.dataAttributes = (' data-parent-id="' + _parentOrgId + '"  data-parent-name="' + _parentOrg.name + '" ');
                    }
                    if (orgsList[item.id].children.length > 0) {
                        if (_isTopLevel) {
                            attrObj.textClass = "text-muted";
                        } else {
                            attrObj.textClass = "text-muter";
                        }
                    } else {
                        if (_isTopLevel) {
                            attrObj.textClass = "text-muted singleton";
                        } else {
                            attrObj.textClass = "child-item";
                        }
                    }
                    childClinic = `<div id="${item.id}_container" ${attrObj.dataAttributes} class="indent org-container ${attrObj.containerClass}">
                        <label id="org-label-${item.id}" class="org-label ${attrObj.textClass}">
                        <input class="clinic" type="checkbox" name="organization" id="${item.id}_org" data-org-name="${item.name}" data-short-name="${item.shortname || item.name}" state="${state ? state : ''}" value="${item.id}" ${attrObj.dataAttributes} />
                        <span>${item.name}</span></label></div>`;
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
    OrgTool.prototype.populateOrgsStateSelector = function(subjectId, parentOrgsToDraw, callback) {
        var self = this; /*global i18next */
        callback = callback || function() {};
        parentOrgsToDraw = parentOrgsToDraw || [];
        var stateDict={AL: i18next.t("Alabama"),AK: i18next.t("Alaska"), AS: i18next.t("American Samoa"),AZ: i18next.t("Arizona"),AR:i18next.t("Arkansas"),CA: i18next.t("California"),CO:i18next.t("Colorado"),CT:i18next.t("Connecticut"),DE:i18next.t("Delaware"),DC:i18next.t("District Of Columbia"),FM: i18next.t("Federated States Of Micronesia"),FL:i18next.t("Florida"),GA:i18next.t("Georgia"),GU:i18next.t("Guam"),HI:i18next.t("Hawaii"),ID:i18next.t("Idaho"),IL:i18next.t("Illinois"),IN:i18next.t("Indiana"),IA:i18next.t("Iowa"),KS:i18next.t("Kansas"),KY:i18next.t("Kentucky"),LA:i18next.t("Louisiana"),ME:i18next.t("Maine"),MH:i18next.t("Marshall Islands"),MD:i18next.t("Maryland"),MA:i18next.t("Massachusetts"),MI:i18next.t("Michigan"),MN:i18next.t("Minnesota"),MS:i18next.t("Mississippi"),MO:i18next.t("Missouri"),MT:i18next.t("Montana"),NE: i18next.t("Nebraska"),NV:i18next.t("Nevada"),NH:i18next.t("New Hampshire"),NJ:i18next.t("New Jersey"),NM:i18next.t("New Mexico"),NY:i18next.t("New York"),NC:i18next.t("North Carolina"),ND:i18next.t("North Dakota"),MP:i18next.t("Northern Mariana Islands"),OH:i18next.t("Ohio"),OK:i18next.t("Oklahoma"),OR:i18next.t("Oregon"),PW:i18next.t("Palau"),PA:i18next.t("Pennsylvania"),PR:i18next.t("Puerto Rico"),RI:i18next.t("Rhode Island"),SC:i18next.t("South Carolina"),SD:i18next.t("South Dakota"),TN:i18next.t("Tennessee"),TX:i18next.t("Texas"),UT:i18next.t("Utah"),VT:i18next.t("Vermont"),VI:i18next.t("Virgin Islands"),VA:i18next.t("Virginia"),WA:i18next.t("Washington"),WV:i18next.t("West Virginia"),WI:i18next.t("Wisconsin"),WY:i18next.t("Wyoming")};
        var getParentState = (o, states) => {
            if (!o) {
                return "";
            }
            var s = "", found = false;
            for (var state in states) {
                if (!found) {
                    (states[state]).forEach(function(i) {
                        if (String(i) === String(o)) {
                            s = state;
                            found = true;
                        }
                    });
                }
            }
            return s;
        };
        $("#stateSelector").on("change", function() {
            let selectedState = $(this).find("option:selected");
            let container = $("#" + selectedState.val() + "_container");
            let defaultPrompt = i18next.t("What is your main clinic for prostate cancer care");
            $("#userOrgsInfo").hide();
            if (selectedState.val() !== "") {
                if (selectedState.val() === "none") {
                    $(".state-container, .noOrg-container").hide();
                    $(".clinic-prompt").text("").hide();
                    $("#noOrgs").prop("checked", true).trigger("click");
                    //send of ajax to update org to 0 here
                } else {
                    if (container.length > 0) {
                        $(".state-container").hide();
                        $(".clinic-prompt").text(defaultPrompt + " in " + selectedState.text() + "?").show();
                        $(".noOrg-container").show();
                        $("#noOrgs").prop("checked", false);
                        container.show();
                    } else {
                        $(".state-container, .clinic-prompt, .noOrg-container").hide();
                        $("#userOrgsInfo").show();
                    }
                }
            } else {
                $(".state-container, .noOrg-container").hide();
                $(".clinic-prompt").text("").hide();
            }
        });

        var orgsList = this.orgsList, states = {}, contentHTML = "";
        /**** draw state select element first to gather all states - assign orgs to each state in array ***/
        (self.orgsData).forEach(function(item) {
            let __state = "";
            if (!item.identifier) { return false; }
            (item.identifier).forEach(function(region) {
                if (String(region.system) === String(SYSTEM_IDENTIFIER_ENUM.practice_region) && region.value) {
                    __state = (region.value).split(":")[1];
                    if (!states.hasOwnProperty(__state)) {
                        states[__state] = [item.id];
                        $("#userOrgs .main-state-container").prepend("<div id='" + __state + "_container' state='" + __state + "' class='state-container'></div>");
                    } else {
                        (states[__state]).push(item.id);
                    }
                    if ($("#stateSelector option[value='" + __state + "']").length === 0) {
                        $("#stateSelector").append("<option value='" + __state + "'>" + stateDict[__state] + "</option>");
                    }
                    orgsList[item.id].state = __state; //assign state for each item
                }
            });
        });

        /*
            * If an organization is a top level org and has child orgs, we render legend for it.  This will prevent the organization from being selected by the user.
            * Note: a hidden input field is rendered for the organization so it can still be referenced by the child orgs if necessary.
            */
        var parentOrgs = $.grep(this.orgsData, function(item) {
            return parseInt(item.id) !== 0 && !item.partOf;
        });

        parentOrgs = parentOrgs.sort(function(a, b) { //sort parent orgs so ones with children displayed first
            var oo_1 = orgsList[a.id];
            var oo_2 = orgsList[b.id];
            if (oo_1 && oo_2) {
                if (oo_1.children.length > 0 && oo_2.children.length > 0) {
                    if (a.name < b.name) {
                        return -1;
                    }
                    if (a.name > b.name) {
                        return 1;
                    }
                    return 0;
                } else if (oo_1.children.length > 0 && oo_2.children.length === 0) {
                    return -1;
                } else if (oo_2.children.length > 0 && oo_1.children.length === 0) {
                    return 1;
                } else {
                    if (a.name < b.name) {
                        return -1;
                    }
                    if (a.name > b.name) {
                        return 1;
                    }
                    return 0;
                }
            } else {
                return 0;
            }
        });
        parentOrgs.forEach(function(item) {
            var state = orgsList[item.id].state;
            if ($("#" + state + "_container").length > 0) {
                var oo = orgsList[item.id];
                contentHTML = `<div class="item">`;
                if (!(parentOrgsToDraw.indexOf(item.name) !== -1) && oo.children.length > 0) {
                    contentHTML += `<legend orgId="${item.id}">${item.name}</legend><input class="tnth-hide" type="checkbox" name="organization" parent_org="true" data-org-name="${item.name}"  id="${item.id}_org" value="${item.id}" />`;
                } else { //also need to check for top level orgs that do not have children and render those
                    contentHTML += `
                    <div class="radio parent-singleton">
                        <legend orgId="${item.id}" class="singleton">${item.name}</legend>
                        <label><input class="clinic" type="radio" id="${item.id}_org" value="${item.id}" state="${state}" name="organization" data-parent-name="${item.name}" data-parent-id="${item.id}">${i18next.t(item.name)}</label></div>`;
                }
                contentHTML += `</div>`;
                $("#" + state + "_container").append(contentHTML);
            }
        });

        var childOrgs = $.grep(this.orgsData, function(item) { //draw input element(s) that belongs to each state based on parent organization id
            return parseInt(item.id) !== 0 && item.partOf;
        });

        childOrgs = childOrgs.sort(function(a, b) { //// sort child clinics in alphabetical order
            if (a.name < b.name) {
                return 1;
            }
            if (a.name > b.name) {
                return -1;
            }
            return 0;
        });
        childOrgs.forEach(function(item) {
            var parentId = (item.partOf.reference).split("/")[2];
            if (parentId) {
                if (parentOrgsToDraw.indexOf(self.getOrgName(parentId)) !== -1) {
                    return true;
                }
                var parentState = getParentState(parentId, states);
                contentHTML = `<div class="radio"><label class="indent"><input class="clinic" type="radio" id="${item.id}_org" value="${item.id}" state="${parentState}" name="organization" data-parent-name="${item.name}" data-parent-id="${parentId}">${i18next.t(item.name)}</label></div>`;
                if ($("#" + parentState + "_container legend[orgId='" + parentId + "']").length > 0) {
                    $("#" + parentState + "_container legend[orgId='" + parentId + "']").after(contentHTML);
                } else {
                    $("#" + parentState + "_container").append(contentHTML);
                }
            }
        });
        //var selectOptions = $("#stateSelector").sortOptions();
        var selectOptions = $("#stateSelector option");
        if (selectOptions.length > 0) {
            var selectSortedOptions = $("#stateSelector").sortOptions();
            if (selectSortedOptions && selectSortedOptions.length > 0) { //sorting the select options
                $("#stateSelector").empty().append(selectSortedOptions)
                    .append(`<option value="none">${i18next.t("Other")}</option>`)
                    .prepend(`<option value="" selected>${i18next.t("Select")}</option>`)
                    .val("");
            }
            $(".state-container, .clinic-prompt").hide();
            setTimeout(function() { //case of pre-selected clinic, need to check if any clinic has prechecked
                var o = $("#userOrgs input[name='organization']:checked");
                if (o.length > 0 && parseInt(o.val()) !== 0) {
                    o.closest(".state-container").show();
                    $(".clinic-prompt").show();
                }
            }, 150);
            $("#userOrgs input[name='organization']").each(function() {
                if (parseInt($(this).val()) !== 0) {
                    Consent.getDefaultModal(this);
                }
            });
            self.onLoaded(subjectId, false);
        } else { // if no states found, then need to draw the orgs UI
            $("#userOrgs .selector-show").hide();
            self.onLoaded(subjectId, true);
            self.filterOrgs(self.getHereBelowOrgs());
            self.morphPatientOrgs();
            $(".noOrg-container, .noOrg-container *").show();
        }
        $("#clinics").attr("loaded", true);
        callback();
    };
    OrgTool.prototype.handleOrgsEvent = function(userId, isConsentWithTopLevelOrg) {
        var self = this;
        $("#userOrgs input[name='organization']").each(function() {
            $(this).attr("data-save-container-id", "userOrgs");
            $(this).on("click", function() {
                var parentOrg = self.getElementParentOrg(this);
                var orgsElements = $("#userOrgs input[name='organization']").not("[id='noOrgs']");
                if ($(this).prop("checked")) {
                    if ($(this).attr("id") !== "noOrgs") {
                        $("#noOrgs").prop("checked", false);
                    } else {
                        orgsElements.prop("checked", false);
                    }
                }
                $("#userOrgs .help-block").removeClass("error-message").text("");
                if (sessionStorage.getItem("noOrgModalViewed")) {
                    sessionStorage.removeItem("noOrgModalViewed");
                }

                if ($(this).attr("id") !== "noOrgs" && $("#fillOrgs").attr("patient_view")) {
                    if (tnthAjax.hasConsent(userId, parentOrg)) {
                        self.updateOrgs(userId, $("#clinics"), true);
                        return;
                    }
                    var __modal = Consent.getConsentModal(parentOrg);
                    if (__modal && __modal.length > 0) {
                        setTimeout(function() { __modal.modal("show"); }, 50);
                        return;
                    }
                    self.updateOrgs(userId, $("#clinics"), true);
                    setTimeout(function() { Consent.setDefaultConsent(userId, parentOrg);}, 500);
                    return;
                }
                self.updateOrgs(userId, $("#clinics"),true);
                var thisElement = $(this);
                setTimeout(function() {
                    Consent.setConsentBySelectedOrg(userId, thisElement, isConsentWithTopLevelOrg);
                }, 500);
            });
        });
    };
    OrgTool.prototype.getOrgsByCareProvider = function(data) {
        if (!data) return false;
        let cloneSet = [...data];
        let orgFilteredSet = cloneSet.filter(item => {
            return item.reference.match(/^api\/organization/gi);
        });
        if (!orgFilteredSet.length) return false;
        return orgFilteredSet.map(item => {
            return item.reference.split("/")[2];
        });
    };
    OrgTool.prototype.setOrgsVis = function(data, callback) {
        callback = callback || function() {};
        if (!data || ! data.careProvider) { callback(); return false;}
        let orgsSet = this.getOrgsByCareProvider(data.careProvider);
        if (!orgsSet || !orgsSet.length) return false;
        for (var i = 0; i < orgsSet.length; i++) {
           let orgID = orgsSet[i];
            if (parseInt(orgID) === 0) {
                $("#userOrgs #noOrgs").prop("checked", true);
                if ($("#stateSelector").length > 0) {
                    $("#stateSelector").find("option[value='none']").prop("selected", true).val("none");
                }
            } else {
                var ckOrg = $("#userOrgs input.clinic[value=" + orgID + "]");
                if ($(".state-container").length) {
                    if (ckOrg.length) {
                        ckOrg.prop("checked", true);
                        var state = ckOrg.attr("state");
                        if (state) {
                            $("#stateSelector").find("option[value='" + state + "']").prop("selected", true).val(i18next.t(state));
                        }
                        $("#clinics .state-selector-container").show();
                        $("#stateSelector").trigger("change");
                    }
                    $(".noOrg-container").show();
                } else {
                    if (ckOrg.length) {
                        ckOrg.prop("checked", true);
                    } else {
                        var topLevelOrg = $("#fillOrgs").find("legend[orgid='" + orgID + "']");
                        if (topLevelOrg.length) {
                            topLevelOrg.attr("data-checked", "true");
                        }
                    }
                }
            }
        }
        callback(data);
    };
    OrgTool.prototype.updateOrgs = function(userId, targetField, sync, callback) {
        callback = callback || function() {};
        tnthAjax.getDemo(userId, "", function(existingDemoData) {
            var demoArray = {"resourceType": "Patient"}, preselectClinic = $("#preselectClinic").val();
            if (existingDemoData && existingDemoData.careProvider) {
                //make sure we don't wipe out reference to other than organization
                let cloneSet = [...existingDemoData.careProvider];
                demoArray.careProvider = cloneSet.filter(item => {
                    return !item.reference.match(/^api\/organization/gi);
                });
            } else {
                demoArray.careProvider = [];
            }
            if (preselectClinic) {
                demoArray.careProvider.push({reference: "api/organization/" + preselectClinic}); /* add this regardless of consent */
            } else {
                var orgIDs = $("#userOrgs input[name='organization']:checked").map(function() {
                    return {reference: "api/organization/" + $(this).val()};
                }).get();
                if (orgIDs && orgIDs.length > 0) {
                    demoArray.careProvider = orgIDs;
                }
                /**** dealing with the scenario where user can be affiliated with top level org e.g. TrueNTH Global Registry, IRONMAN, via direct database addition **/
                $("#fillOrgs legend[data-checked]").each(function() {
                    var tOrg = $(this).attr("orgid");
                    if (tOrg) {
                        demoArray.careProvider.push({reference: "api/organization/" + tOrg});
                    }
                });
            }
            if ($("#aboutForm").length === 0 && (!demoArray.careProvider)) { //don't update org to none if there are top level org affiliation above
                demoArray.careProvider.push({reference: "api/organization/" + 0});
            }
            tnthAjax.putDemo(userId, demoArray, targetField, sync, function() {
                $("#clinics").trigger("updated");
                callback();
            });
        });
    };
    OrgTool.prototype.getShortName = function(orgId) {
        var shortName = "";
        if (!orgId) { return shortName; }
        var orgsList = this.getOrgsList();
        var orgItem = orgsList.hasOwnProperty(orgId) ? orgsList[orgId]: {};
        if (orgItem.shortname) {
            shortName = orgItem.shortname;
        }
        return shortName;
    };
    OrgTool.prototype.getSelectedOrgTopLevelParentOrg = function(){
        return this.getTopLevelParentOrg(this.getSelectedOrg().val());
    };
    OrgTool.prototype.getSelectedOrg = function() {
        return $("#userOrgs input[name='organization']:checked");
    };
    OrgTool.prototype.getUserTopLevelParentOrgs = function(uo) {
        var parentList = [], self = this;
        if (!uo) {
            return false;
        }
        if (uo.parentList) { return uo.parentList; }
        uo.forEach(function(o) {
            var p = self.getTopLevelParentOrg(o);
            if (p && !self.inArray(p, parentList)) {
                parentList.push(p);
            }
        });
        uo.parentList = parentList;
        return parentList;
    };
    OrgTool.prototype.getTopLevelParentOrg = function(currentOrg) {
        var ml = this.getOrgsList(), currentOrgItem = ml[currentOrg], self = this;
        if (!currentOrgItem) { return false; }
        if (currentOrgItem.isTopLevel) {
            return currentOrg;
        }
        if (currentOrgItem.parentOrgId) {
            return self.getTopLevelParentOrg(currentOrgItem.parentOrgId);
        }
        return currentOrg;
    };
    OrgTool.prototype.getChildOrgs = function(orgs, orgList) {
        orgList = orgList || [];
        if (!orgs || !orgs.length) {
            return orgList;
        }
        var mainOrgsList = this.getOrgsList(), childOrgs = [];
        orgs.forEach(function(org) {
            var o = mainOrgsList[org.id];
            if (!o) {
                return true;
            }
            orgList.push(org.id);
            var c = o.children ? o.children : null;
            if (c && c.length) {
                c.forEach(function(i) {
                    childOrgs.push(i);
                });
            }
        });
        return this.getChildOrgs(childOrgs, orgList);
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
            var co = mainOrgsList[orgId], cOrgs = self.getChildOrgs((co && co.children ? co.children : []));
            if (cOrgs.length) {
                here_below_orgs = here_below_orgs.concat(cOrgs);
            }
        });
        return here_below_orgs;
    };
    OrgTool.prototype.getLeafOrgs = function(userOrgs, orgList) {
        if (!userOrgs) {
            return [];
        }
        let mainOrgsList = this.getOrgsList(), self = this, currentList = [], childOrgs = [];
        userOrgs.forEach(function(orgId) {
            let orgItem = mainOrgsList[orgId];
            if (!orgItem) {
                return true;
            }
            if (orgItem.children && orgItem.children.length) {
                let arrChildOrgs = orgItem.children.map(item => item.id);
                childOrgs = childOrgs.concat(arrChildOrgs);
            } else {
                currentList.push(orgId);
            }
        });
        orgList = orgList || [];
        orgList = orgList.concat(currentList);
        if (childOrgs.length) {
            return self.getLeafOrgs(childOrgs, orgList);
        }
        return orgList;
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
    return OrgTool;
})();
