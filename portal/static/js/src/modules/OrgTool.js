import SYSTEM_IDENTIFIER_ENUM from "./SYSTEM_IDENTIFIER_ENUM.js";
import tnthAjax from "./TnthAjax.js";
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
        this.TOP_LEVEL_ORGS = [];
        this.orgsList = {};
        this.orgsData = [];
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
                    self.orgsData = data.entry;
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
        return this.orgsList;
    };
    OrgTool.prototype.getOrgName = function(orgId){
        var orgsList = this.getOrgsList();
        if (orgId && orgsList.hasOwnProperty(orgId)) {
            return orgsList[orgId].name;
        }
        return "";
    };
    OrgTool.prototype.filterOrgs = function(leafOrgs) {
        leafOrgs = leafOrgs || [];
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
        if (sessionStorage.orgsHTML) {
            $("#fillOrgs").html(sessionStorage.orgsHTML);
            return true;
        }
        var self = this, container = $("#fillOrgs"), orgsList = this.orgsList, parentContent = "";
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
                    parentContent = `<label id="org-label-${org}" class="org-label">
                        <input class="clinic" type="checkbox" name="organization" parent_org="true" id="${org}_org" state="${parentState}" value="${org}"
                        data-parent-id="${org}"  data-org-name="${parentOrgName}" data-short-name="${orgShortName}" data-parent-name="${parentOrgName}"/><span>${parentOrgName}</span></label></div>`;
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

                    if ($("#fillOrgs input[name='organization'][value='" + item.id + "']").length > 0) {
                        return true;
                    }
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
