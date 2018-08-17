(function() { /*global Vue DELAY_LOADING  hasValue i18next $ */
    DELAY_LOADING = true; //a workaround for hiding of loading indicator upon completion of loading of portal wrapper - loading indicator needs to continue displaying until patients list has finished loading
    $.ajaxSetup({contentType: "application/json; charset=utf-8"});
    var AdminObj = window.AdminObj = new Vue({
        el: "#adminTableContainer",
        errorCaptured: function(Error, Component, info) {
            console.error("Error: ", Error, " Component: ", Component, " Message: ", info); /* console global */
            return false;
        },
        errorHandler: function (err, vm) {
            this.dataError = true;
            var errorElement = document.getElementById("admin-table-error-message");
            if (errorElement) {
                errorElement.innerHTML = "Error occurred initializing Admin Vue instance.";
            }
            console.warn("Admin Vue instance threw an error: ", vm, this);
            console.error("Error thrown: ", err);
        },
        created: function() {
            this.injectDependencies();
            this.getOrgTool();
        },
        mounted: function() {
            var self = this;
            VueErrorHandling(); /* global VueErrorHandling */
            this.preConfig(function() {
                if ($("#adminTable").length > 0) {
                    self.rowLinkEvent();
                    self.setColumnSelections();
                    self.setTableFilters(self.userId); //set user's preference for filter(s)
                    self.initTableEvents();
                    self.initOrgsList();
                    self.handleDisableFields();
                    self.handleDeletedUsersVis();
                    self.setRowItemEvent();
                    self.handleAffiliatedUIVis();
                    self.addFilterPlaceHolders();
                } else {
                    self.initOrgsList();
                    self.handleDownloadModal();
                }
                setTimeout(function() { self.fadeLoader(); }, 350);
            });
        },
        data: {
            dataError: false,
            configured: false,
            initIntervalId: 0,
            sortFilterEnabled: false,
            showDeletedUsers: false,
            isAdmin: false,
            userId: null,
            userRoles: [],
            userOrgs: [],
            topLevelOrgs: [],
            orgTool: null,
            orgsSelector: {
                selectAll: false,
                clearAll: false,
                close: false
            },
            ROW_ID_PREFIX: "data_row_",
            tableIdentifier: "adminList",
            popoverEventInitiated: false,
            dependencies: {},
            tableConfig: {
                formatShowingRows: function(pageFrom, pageTo, totalRows) {
                    var rowInfo;
                    setTimeout(function() {
                        rowInfo = i18next.t("Showing {pageFrom} to {pageTo} of {totalRows} users").replace("{pageFrom}", pageFrom).replace("{pageTo}", pageTo).replace("{totalRows}", totalRows);
                        $(".pagination-detail .pagination-info").html(rowInfo);
                    }, 10);
                    return rowInfo;
                },
                formatRecordsPerPage: function(pageNumber) {
                    return i18next.t("{pageNumber} records per page").replace("{pageNumber}", pageNumber);
                },
                formatToggle: function() {
                    return i18next.t("Toggle");
                },
                formatColumns: function() {
                    return i18next.t("Columns");
                },
                formatAllRows: function() {
                    return i18next.t("All rows");
                },
                formatSearch: function() {
                    return i18next.t("Search");
                },
                formatNoMatches: function() {
                    return i18next.t("No matching records found");
                },
                formatExport: function() {
                    return i18next.t("Export data");
                }
            },
            currentTablePreference: null,
            errorCollection: {orgs: "", demo: ""},
            instruments: {list: [], dataType: "csv", selected: "", message: ""},
            patientReports: {data: [], message: "", loading: false }
        },
        methods: {
            injectDependencies: function() {
                var self = this;
                for (var key in window.portalModules) {
                    if ({}.hasOwnProperty.call(window.portalModules, key)) {
                        self.dependencies[key] = window.portalModules[key];
                    }
                }
            },
            getDependency: function(key) {
                if(key && this.dependencies.hasOwnProperty(key)) {
                    return this.dependencies[key];
                } else {
                    throw Error("Dependency " + key + " not found."); //throw error ? should be visible in console
                }
            },
            showMain: function() {
                $("#mainHolder").css({
                    "visibility": "visible",
                    "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
                    "filter": "alpha(opacity=100)",
                    "-moz-opacity": 1,
                    "-khtml-opacity": 1,
                    "opacity": 1
                });
            },
            setOrgsMenuHeight: function(padding) {
                padding = padding || 85;
                var h = parseInt($("#fillOrgs").height());
                if(h > 0) {
                    var adminTable = $("div.admin-table"), orgMenu = $("#org-menu");
                    var calculatedHeight = h + padding;
                    $("#org-menu").height(calculatedHeight);
                    if(adminTable.height() < orgMenu.height()) {
                        setTimeout(function() { adminTable.height(orgMenu.height() + calculatedHeight);}, 0);
                    }
                }
            },
            clearFilterButtons: function() {
                this.setOrgsSelector({selectAll: false, clearAll: false, close: false});
            },
            fadeLoader: function() {
                DELAY_LOADING = false;
                var self = this;
                setTimeout(function() { self.showMain(); }, 250);
                setTimeout(function() { $("#loadingIndicator").fadeOut();}, 300);
            },
            showLoader: function() {
                $("#loadingIndicator").show();
            },
            preConfig: function(callback) {
                var self = this, tnthAjax = this.getDependency("tnthAjax");
                callback = callback || function() {};
                tnthAjax.getCurrentUser(function(data) {
                    if(data) {
                        self.userId = data.id;
                        self.setIdentifier();
                        self.setSortFilterProp();
                        self.configTable();
                        self.configured = true;
                        setTimeout(function() {callback();}, 50);
                    } else {
                        alert(i18next.t("User Id is required")); /* global i18next */
                        self.configured = true;
                        return false;
                    }
                }, {sync: true});
            },
            setIdentifier: function() {
                var adminTableContainer = $("#adminTableContainer");
                if(adminTableContainer.hasClass("patient-view")) {
                    this.tableIdentifier = "patientList";
                }
                if(adminTableContainer.hasClass("staff-view")) {
                    this.tableIdentifier = "staffList";
                }
            },
            setOrgsSelector: function(obj) {
                if (!obj) { return false; }
                var self = this;
                for (var prop in obj) {
                    if (self.orgsSelector.hasOwnProperty(prop)) {
                        self.orgsSelector[prop] = obj[prop];
                    }
                }
            },
            setSortFilterProp: function() {
                this.sortFilterEnabled = this.tableIdentifier === "patientList";
            },
            configTable: function() {
                var options = {};
                var sortObj = this.getTablePreference(this.userId, this.tableIdentifier);
                sortObj = sortObj || this.getDefaultTablePreference();
                options.sortName = sortObj.sort_field;
                options.sortOrder = sortObj.sort_order;
                options.filterBy = sortObj;
                options.exportOptions = { /* global  __getExportFileName*/
                    fileName: __getExportFileName($("#adminTableContainer").attr("data-export-prefix"))
                };
                $("#adminTable").bootstrapTable(this.getTableConfigOptions(options));
            },
            getTableConfigOptions: function(options) {
                if(!options) {
                    return this.tableConfig;
                } else {
                    return $.extend({}, this.tableConfig, options);
                }
            },
            initTableEvents: function() {
                var self = this;
                $("#adminTable").on("reset-view.bs.table", function() {
                    self.addFilterPlaceHolders();
                    self.resetRowVisByActivationStatus();
                    self.setRowItemEvent();
                });
                $("#adminTable").on("search.bs.table", function() {
                    self.resetRowVisByActivationStatus();
                });
                $("#adminTable").on("page-change.bs.table", function() {
                    if(!$("#patientList .tnth-headline").isOnScreen()) { /*global isOnScreen */
                        $("html, body").animate({  scrollTop: $(".fixed-table-toolbar").offset().top}, 2000);
                    }
                });
                $(window).bind("scroll mousedown mousewheel keyup", function() {
                    if ($("html, body").is(":animated")) {
                        $("html, body").stop(true, true);
                    }
                });
                $("#chkDeletedUsersFilter").on("click", function() {
                    self.handleDeletedUsersVis();
                });
                if(this.sortFilterEnabled) {
                    $("#adminTable").on("sort.bs.table", function(e, name, order) {
                        setTimeout(function() { self.setTablePreference(self.userId, self.tableIdentifier, name, order); }, 10);
                    }).on("column-search.bs.table", function() {
                        setTimeout(function() { self.setTablePreference(self.userId); }, 10);
                    }).on("column-switch.bs.table", function() {
                        setTimeout(function() { self.setTablePreference(self.userId); }, 10);
                    });
                }
            },
            setShowDeletedUsersFlag: function() {
            	if (!$("#chkDeletedUsersFilter").length) {
            		return;
            	}
            	this.showDeletedUsers = $("#chkDeletedUsersFilter").is(":checked");
            },
            handleDeletedUsersVis: function() {
                this.setShowDeletedUsersFlag();
                if (this.showDeletedUsers) {
                    $("#adminTable").bootstrapTable("filterBy", {activationstatus: "deactivated"});
                } else {
                    $("#adminTable").bootstrapTable("filterBy", {activationstatus: "activated"});
                }
            },
            handleAffiliatedUIVis: function() {
                $("#adminTableContainer input[data-field='id']:checkbox, #adminTableContainer input[data-field='deactivate']:checkbox, #adminTableContainer input[data-field='deleted']:checkbox").closest("label").hide(); //hide checkbox for hidden id field and deactivate account field from side menu
                $("#patientReportModal").modal({"show": false});
            },
            setRowItemEvent: function() {
                var self = this;
                $("#adminTableContainer .btn-report:not(.has-click-handelr)").on("click", function(e) {
                    e.stopPropagation();
                    self.getReportModal($(this).attr("data-patient-id"), {documentDataType:$(this).attr("data-document-type")});
                }).addClass(".has-click-handler");
                $("#adminTableContainer .btn-delete-user").each(function(){
                    $(this).popover({
                        container: "#adminTable",
                        html: true,
                        content: ["<div>{title}</div>",
                                	"<div class='buttons-container'>",
                                	"<button class='btn btn-small btn-default popover-btn-deactivate' data-user-id='{userid}'>{yes}</button>&nbsp;",
                                	"<button class='btn btn-small btn-default popover-btn-cancel'>{no}</button>",
                                	"</div>"
                                ].join("")
                                .replace("{title}", i18next.t("Are you sure you want to deactivate this account?"))
                                .replace(/\{userid\}/g, $(this).attr("data-user-id"))
                                .replace("{yes}", i18next.t("Yes"))
                                .replace("{no}", i18next.t("No")),
                        placement: "top"
                    });
                    $(this).off("click").on("click", function(e) {
                        e.stopPropagation();
                        $(this).popover("show");
                        var userId = $(this).attr("data-user-id");
                        if (!($("#data-delete-loader-"+userId).length)) {
                        	$(this).parent().append("<i id=\"data-delete-loader-{userid}\" class=\"fa fa-spinner tnth-hide\"></i>".replace("{userid}", userId));
                        }
                    });
                });
                $(document).off("click.popover-btn-deactivate").on("click", ".popover-btn-deactivate", function(e) {
                    e.stopPropagation();
                    var userId = $(this).attr("data-user-id");
                    var loader = $("#data-delete-loader-" + userId);
                    loader.show();
                    $("#btnDeleted"+userId).hide();
                    $(this).closest(".popover").popover("hide");
                    setTimeout(function() {
                    	self.deactivateUser(userId, !self.showDeletedUsers, function() {
                    		loader.hide();
                    		$("#btnDeleted"+userId).show();
                    	});
                    }, 150);
                });
                $("#adminTable .reactivate-icon").off("click").on("click", function(e) {
                    e.stopPropagation();
                    self.reactivateUser($(this).attr("data-user-id"));
                });

                $(document).on("click", ".popover-btn-cancel", function(e) {
                    e.stopPropagation();
                    $(this).closest(".popover").popover("hide");
                });
                $(document).on("click", function() {
                    $("#adminTable .popover").popover("hide");
                });
            },
            addFilterPlaceHolders: function() {
                $("#adminTable .filterControl input").attr("placeholder", i18next.t("Enter Text"));
                $("#adminTable .filterControl select option[value='']").text(i18next.t("Select"));
            },
            handleMedidataRave: function(params) {
                if (!$("#adminTableContainer").hasClass("patient-view")) { //check if this is a patients list
                    return false;
                }
                var self = this, tnthAjax = this.getDependency("tnthAjax");
                params = params||{};
                tnthAjax.sendRequest("/api/settings", "GET", this.userId, params, function(data) {
                    if (!data || data.error || !data.MEDIDATA_RAVE_ORG) {
                        return false;
                    }
                    var match = $.grep(self.topLevelOrgs, function(org) {
                        return data.MEDIDATA_RAVE_ORG === org;
                    });
                    if (match.length === 0) {
                        return false;
                    }
                    self.setCreateAccountVis(true);
                    self.checkAdmin();
                });
            },
            setCreateAccountVis: function(hide) {
                var createAccountElements = $("#patientListOptions .or, #createUserLink");
                if (hide) {
                    createAccountElements.css("display", "none");
                    return;
                }
                createAccountElements.css("display", "block");
            },
            getUserRoles: function(callback) {
                callback = callback || function() {};
                if (this.userRoles.length > 0) {
                    callback(this.userRoles);
                    return;
                }
                this.setUserRoles(callback);
            },
            setUserRoles: function(callback) {
                callback = callback || function() {};
                var self = this, tnthAjax = this.getDependency("tnthAjax");
                tnthAjax.getRoles(this.userId, function(data) {
                    if (!data || data.error) {
                        callback({"error": i18next.t("Error occurred setting user roles")});
                        return false;
                    }
                    self.userRoles = data.roles.map(function(item) {
                        return item.name;
                    });
                    self.isAdmin = self.userRoles.indexOf("admin") !== -1;
                    callback();
                });
            },
            checkAdmin: function() {
                var self = this;
                this.getUserRoles(function() {
                    if (self.isAdmin) {
                        self.setCreateAccountVis(); //allow admin user to create account
                    }
                });
            },
            handleDisableFields: function() {
                this.handleMedidataRave(); //a function specifically created to handle MedidataRave related stuff
                //can do other things related to disabling fields here if need be
            },
            setUserOrgs: function() {
                if(!this.userId) { return false; }
                var self = this;
                $.ajax({
                    type: "GET",
                    async: false,
                    url: "/api/demographics/" + this.userId
                }).done(function(data) {
                    if(data && data.careProvider) {
                        self.userOrgs = (data.careProvider).map(function(val) {
                            var orgID = val.reference.split("/").pop();
                            if(parseInt(orgID) === 0) { $("#createUserLink").attr("disabled", true);}
                            return orgID;
                        });
                        if(self.userOrgs.length === 0) {
                            $("#createUserLink").attr("disabled", true);
                        }
                    }
                }).fail(function() {
                    alert(i18next.t("Error occurred setting user organizations"));
                });
            },
            getUserOrgs: function() {
                if(this.userOrgs.length === 0) {
                    this.setUserOrgs(this.userId);
                }
                return this.userOrgs;
            },
            getOrgTool: function() {
                if (!this.orgTool) {
                    this.orgTool = new (this.getDependency("orgTool")) ();
                }
                return this.orgTool;
            },
            setTopLevelOrgs: function() {
                var self = this;
                this.topLevelOrgs = (this.userOrgs).map(function(orgId) {
                    return self.orgTool.getOrgName(self.orgTool.getTopLevelParentOrg(orgId));
                });
            },
            initOrgsList: function() {
                if($("#orglistSelector").length === 0) {
                    return false;
                }
                var self = this;
                this.setUserOrgs();
                this.orgTool.init(function(data) {
                    if (data.error) {
                        self.errorCollection.orgs = i18next.t("Error occurred retrieving data from server.");
                        self.fadeLoader();
                        return false;
                    } else {
                        self.errorCollection.orgs = "";
                    }
                    self.setTopLevelOrgs();
                    self.orgTool.populateUI(); //populate orgs dropdown UI
                    var hbOrgs = self.orgTool.getHereBelowOrgs(self.getUserOrgs()); //filter orgs UI based on user's orgs
                    self.orgTool.filterOrgs(hbOrgs);
                    self.initOrgsFilter();
                    self.initOrgsEvent();
                    self.fadeLoader();
                });
            },
            siteFilterApplied: function() {
                return this.currentTablePreference
                    && this.currentTablePreference.filters
                    && this.currentTablePreference.filters.orgs_filter_control
                    && this.currentTablePreference.filters.orgs_filter_control.length;
            },
            initOrgsFilter: function() {
                var orgFields = $("#userOrgs input[name='organization']");
                var fi = this.currentTablePreference ? this.currentTablePreference.filters : {};
                var fa = fi && fi.orgs_filter_control ? fi.orgs_filter_control.split(",") : null;
                orgFields.each(function() {
                    $(this).prop("checked", false);
                    if(!fa) {
                        return true;
                    }
                    var oself = $(this), val = oself.val();
                    fa = fa.map(function(item) {
                        return String(item);
                    });
                    oself.prop("checked", fa.indexOf(String(val)) !== -1);
                });
                if(this.orgTool.getHereBelowOrgs(this.getUserOrgs()).length === 1) {
                    orgFields.prop("checked", true);
                }
            },
            initOrgsEvent: function() {
                var ofields = $("#userOrgs input[name='organization']");
                if (ofields.length === 0) { return false;}
                var self = this;

                $("#orglistSelector .orgs-filter-warning").popover();

                $("body").on("click", function(e) {
                    if ($(e.target).closest("#orglistSelector").length === 0) {
                        $("#orglistSelector").removeClass("open");
                    }
                });

                $("#orglist-dropdown").on("click touchstart", function() {
                    $(this).find(".glyphicon-menu-up, .glyphicon-menu-down").toggleClass("tnth-hide"); //toggle menu up/down button
                    setTimeout(function() {
                        self.setOrgsMenuHeight(95);
                        self.clearFilterButtons();
                    }, 100);
                });
                /* attach orgs related events to UI components */
                ofields.each(function() {
                    $(this).on("click touchstart", function(e) {
                        e.stopPropagation();
                        if($(this).is(":checked")) {
                            var childOrgs = self.orgTool.getHereBelowOrgs([$(this).val()]);
                            if(childOrgs && childOrgs.length > 0) {
                                childOrgs.forEach(function(org) {
                                    $("#userOrgs input[name='organization'][value='" + org + "']").prop("checked", true);
                                });
                            }
                        }
                        self.setOrgsSelector({selectAll: false, clearAll: false, close: false});
                        self.setTablePreference(self.userId, self.tableIdentifier);
                        setTimeout(function() {
                            self.showLoader();
                            location.reload();
                        }, 150);
                    });
                });
                $("#orglist-selectall-ckbox").on("click touchstart", function(e) {
                    e.stopPropagation();
                    var orgsList = [];
                    self.setOrgsSelector({selectAll: true, clearAll: false, close: false});
                    $("#userOrgs input[name='organization']").filter(":visible").each(function() {
                        if($(this).css("display") !== "none") {
                            $(this).prop("checked", true);
                            orgsList.push($(this).val());
                        }
                    });
                    self.setTablePreference(self.userId, self.tableIdentifier); //pre-set user preference for filtering
                    if(orgsList.length > 0) {
                        setTimeout(function() {
                            self.showLoader();
                            location.reload();
                        }, 150);
                    }
                });
                $("#orglist-clearall-ckbox").on("click touchstart", function(e) {
                    e.stopPropagation();
                    self.clearOrgsSelection();
                    self.setOrgsSelector({selectAll: false, clearAll: true, close: false});
                    self.setTablePreference(self.userId, self.tableIdentifier);
                    setTimeout(function() {
                        self.showLoader();
                        location.reload();
                    }, 150);
                });
                $("#orglist-close-ckbox").on("click touchstart", function(e) {
                    e.stopPropagation();
                    self.setOrgsSelector({selectAll: false, clearAll: false, close: true});
                    $("#orglistSelector").trigger("click");
                    return false;
                });
            },
            getInstrumentList: function() {
                var self = this, tnthAjax = this.getDependency("tnthAjax");
                tnthAjax.getInstrumentsList(true, function(data) {
                    if(!data || data.error) {
                        return false;
                    }
                    var instrumentList = data;
                    var parentOrgList = self.orgTool.getUserTopLevelParentOrgs(self.getUserOrgs());
                    if(instrumentList && parentOrgList && parentOrgList.length > 0) {
                        var instrumentItems = [];
                        parentOrgList.forEach(function(o) {
                            if(instrumentList.hasOwnProperty(o)) {
                                instrumentList[o].forEach(function(n) {
                                    instrumentItems.push(n);
                                });
                            }
                        });
                        self.instruments.data = instrumentItems;
                        if(instrumentItems.length > 0) {
                            $(".instrument-container").hide();
                            var found = false;
                            instrumentItems.forEach(function(item) {
                                var instrumentContainer = $("#" + item + "_container");
                                found = instrumentContainer.length > 0;
                                if(found) {
                                    instrumentContainer.show();
                                }
                            });
                            if(!found) {
                                $(".instrument-container").show();
                            }
                        }
                    }
                });
            },
            setInstruments: function(event) {
                if (event.target.value && $(event.target).is(":checked")) {
                    this.instruments.selected = this.instruments.selected + (this.instruments.selected !== "" ? "&" : "") + "instrument_id=" + event.target.value;
                } else {
                    if ($("input[name=instrument]:checked").length === 0) {
                        this.instruments.selected = "";
                    }
                }
            },
            setDataType: function(event) {
                this.instruments.showMessage = false;
                this.instruments.dataType = event.target.value;
            },
            hasInstrumentsSelection: function() {
                return this.instruments.selected !== "" && this.instruments.dataType !== "";
            },
            handleDownloadModal: function() {
                if ($("#dataDownloadModal").length === 0) {
                    return false;
                }
                var self = this;
                this.getInstrumentList();
                $("#dataDownloadModal").on("shown.bs.modal", function() { //populate instruments list based on user's parent org
                    self.instruments.selected = "";
                    self.instruments.dataType = "csv";
                    $("#patientsInstrumentList").addClass("ready");
                });
            },
            clearOrgsSelection: function() {
                $("#userOrgs input[name='organization']").prop("checked", false);
                this.clearFilterButtons();
            },
            getDefaultTablePreference: function() {
                return {
                    sort_field: "id",
                    sort_order: "desc"
                };
            },
            getTablePreference: function(userId, tableName, setFilter, setColumnSelections) {
                if(this.currentTablePreference) { return this.currentTablePreference; }
                var prefData = null, self = this, uid = userId || self.userId;
                var tableIdentifier = tableName || self.tableIdentifier;
                var tnthAjax = self.getDependency("tnthAjax");

                tnthAjax.getTablePreference(uid, tableIdentifier, {
                    "sync": true
                }, function(data) {
                    if (!data || data.error) {
                        return false;
                    }
                    prefData = data || self.getDefaultTablePreference();
                    self.currentTablePreference = prefData;

                    if(setFilter) { //set filter values
                        self.setTableFilters(uid);
                    }
                    if(setColumnSelections) { //set column selection(s)
                        self.setColumnSelections();
                    }
                });
                return prefData;
            },
            setColumnSelections: function() {
                if(!this.sortFilterEnabled) { return false; }
                var prefData = this.getTablePreference(this.userId, this.tableIdentifier);
                var hasColumnSelections = prefData && prefData.filters && prefData.filters.column_selections;
                if (!hasColumnSelections) {
                    return false;
                }
                var visibleColumns = $("#adminTable").bootstrapTable("getVisibleColumns");
                visibleColumns.forEach(function(c) { //hide visible columns
                    if (String(c.class).toLowerCase() === "always-visible") {
                        return true;
                    }
                    $("#adminTable").bootstrapTable("hideColumn", c.field);
                });
                prefData.filters.column_selections.forEach(function(column) { //show column(s) based on preference
                    $(".fixed-table-toolbar input[type='checkbox'][data-field='" + column + "']").prop("checked", true);
                    $("#adminTable").bootstrapTable("showColumn", column);
                });
            },
            setTableFilters: function(userId) {
                var prefData = this.currentTablePreference, tnthAjax = this.getDependency("tnthAjax");
                if (!prefData) {
                    tnthAjax.getTablePreference(userId || this.userId, this.tableIdentifier, {
                        "sync": true
                    }, function(data) {
                        if (!data || data.error) {
                            return false;
                        }
                        prefData = data;
                    });
                }
                if(prefData && prefData.filters) { //set filter values
                    var fname="";
                    for(var item in prefData.filters) {
                        fname = "#adminTable .bootstrap-table-filter-control-" + item;
                        if($(fname).length === 0) {
                            continue;
                        }
                        //note this is based on the trigger event for filtering specify in the plugin
                        $(fname).val(prefData.filters[item]);
                        $(fname).trigger($(fname).get(0).tagName === "INPUT" ? "keyup" : "change");
                    }
                }
            },
            setTablePreference: function(userId, tableName, sortField, sortOrder, filters) {
                var tnthAjax = this.getDependency("tnthAjax");
                tableName = tableName || this.tableIdentifier;
                if (!tableName) {
                    return false;
                }
                userId = userId || this.userId;
                var data = this.getDefaultTablePreference();
                if(hasValue(sortField) && hasValue(sortOrder)) {
                    data["sort_field"] = sortField;
                    data["sort_order"] = sortOrder;
                } else {
                    //get selected sorted field information on UI
                    var sortedField = $("#adminTable th[data-field]").has(".sortable.desc, .sortable.asc");
                    if(sortedField.length > 0) {
                        data["sort_field"] = sortedField.attr("data-field");
                        var sortedOrder = "desc";
                        sortedField.find(".sortable").each(function() {
                            if($(this).hasClass("desc")) {
                                sortedOrder = "desc";
                            } else if($(this).hasClass("asc")) {
                                sortedOrder = "asc";
                            }
                        });
                        data["sort_order"] = sortedOrder;
                    }
                }
                var __filters = filters || {};

                //get fields
                if(Object.keys(__filters).length === 0) {
                    $("#adminTable .filterControl select, #adminTable .filterControl input").each(function() {
                        if(hasValue($(this).val())) {
                            var field = $(this).closest("th").attr("data-field");
                            __filters[field] = $(this).get(0).nodeName.toLowerCase() === "select" ? $(this).find("option:selected").text() : $(this).val();
                        }
                    });
                }
                //get selected orgs from the filter list by site control
                var selectedOrgs = "";
                $("#userOrgs input[name='organization']").each(function() {
                    if($(this).is(":checked") && ($(this).css("display") !== "none")) {
                        selectedOrgs += (hasValue(selectedOrgs) ? "," : "") + $(this).val();
                    }
                });
                __filters["orgs_filter_control"] = selectedOrgs;
                //get column selections
                __filters["column_selections"] = [];
                $(".fixed-table-toolbar input[type='checkbox'][data-field]:checked").each(function() {
                    __filters["column_selections"].push($(this).attr("data-field"));
                });
                data["filters"] = __filters;
                if(Object.keys(data).length > 0) {
                    tnthAjax.setTablePreference(userId, this.tableIdentifier, {"data": JSON.stringify(data)});
                    this.currentTablePreference = data;
                }
            },
            getReportModal: function(patientId, options) {
                $("#patientReportModal").modal("show");
                this.patientReports.loading = true;
                var self = this, tnthDates = self.getDependency("tnthDates"), tnthAjax = self.getDependency("tnthAjax");
                options = options || {};
                tnthAjax.patientReport(patientId, options, function(data) {
                    self.patientReports.data = [];
                    if (!data || data.error) {
                        self.patientReports.message = i18next.t("Error occurred retrieving patient report");
                        return false;
                    }
                    if(data["user_documents"] && data["user_documents"].length > 0) {
                        var existingItems = {}, count = 0;
                        var documents = data["user_documents"].sort(function(a, b) { //sort to get the latest first
                            return new Date(b.uploaded_at) - new Date(a.uploaded_at);
                        });
                        documents.forEach(function(item) {
                            var c = item["contributor"];
                            if(!existingItems[c] && hasValue(c)) { //only draw the most recent, same report won't be displayed
                                if(options.documentDataType && String(options.documentDataType).toLowerCase() !== String(c).toLowerCase()) {
                                    return false;
                                }
                                self.patientReports.data.push({
                                    contributor: item.contributor,
                                    fileName: item.filename,
                                    date: tnthDates.formatDateString(item.uploaded_at, "iso"),
                                    download: "<a title='" + i18next.t("Download") + "' href='" + "/api/user/" + item["user_id"] + "/user_documents/" + item["id"] + "'><i class='fa fa-download'></i></a>"
                                });
                                existingItems[c] = true;
                                count++;
                            }
                        });
                        if(count > 1) {
                            $("#patientReportModal .modal-title").text(i18next.t("Patient Reports"));
                        } else {
                            $("#patientReportModal .modal-title").text(i18next.t("Patient Report"));
                        }
                        self.patientReports.message = "";
                        $("#patientReportContent .btn-all").attr("href", "patient_profile/" + patientId + "#profilePatientReportTable");

                    } else {
                        self.patientReports.message = i18next.t("No report data found.");
                    }
                    setTimeout(function() {
                        self.patientReports.loading = false;
                    }, 550);
                });
            },
            rowLinkEvent: function() {
                $("#admin-table-body.data-link").delegate("tr", "click", function(e) {
                    if(e.target && (e.target.tagName.toLowerCase() !== "td")) {
                        if(e.target.tagName.toLowerCase() === "a" && e.target.click) {
                            return;
                        }
                    }
                    e.preventDefault();
                    e.stopPropagation();
                    var row = $(this).closest("tr");
                    if(!row.hasClass("no-records-found")) {
                        $("#adminTable .popover").popover("hide");
                        document.location = $(this).closest("tr").attr("data-link");
                    }
                });
            },
            deactivationEnabled: function() {
                return $("#chkDeletedUsersFilter").length > 0;
            },
            reactivateUser: function(userId) {
                var tnthAjax = this.getDependency("tnthAjax"), self = this;
                if (!this.isDeactivatedRow(userId)) {
                    return false;
                }
                tnthAjax.reactivateUser(userId, {"async": false}, function(data) {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    self.handleReactivatedRow(userId);
                });
            },
            deactivateUser: function(userId, hideRow, callback) {
            	callback = callback || function() {};
                if (!userId) {
                	callback({error: i18next.t("User id is required.")});
                    return false;
                }
                if (this.isDeactivatedRow(userId)) {
                	callback();
                    return false;
                }
                var tnthAjax = this.getDependency("tnthAjax"), self = this;
                tnthAjax.deactivateUser(userId, {"async": false}, function(data) {
                    if (data.error) {
                    	callback({error: data.error});
                        alert(data.error);
                        return;
                    }
                    callback();
                    if(hideRow) {
                        $("#" + self.ROW_ID_PREFIX + userId).fadeOut();
                    }
                    self.handleDeactivatedRow(userId);
                });
            },
            getRowData: function(userId) {
                if (!userId) {
                    return false;
                }
                return $("#adminTable").bootstrapTable("getRowByUniqueId", userId);
            },
            isDeactivatedRow: function(userId) {
                var rowData = this.getRowData(userId);
                return rowData && String(rowData.activationstatus).toLowerCase() === "deactivated";
            },
            resetRowVisByActivationStatus: function() {
                var self = this;
                $("#adminTable [data-index]").each(function() {
                    var userId = $(this).attr("data-uniqueid");
                    if (self.isDeactivatedRow(userId)) {
                        self.handleDeactivatedRowVis(userId);
                    } else {
                        self.handleReactivatedRowVis(userId);
                    }
                });
            },
            updateFieldData: function(userId, data) {
                if (!userId || !data) {
                    return false;
                }
                $("#adminTable").bootstrapTable("updateCell", data);
            },
            getRowIndex: function(userId) {
                if (!userId) {
                    return false;
                }
                return $("#" + this.ROW_ID_PREFIX + userId).attr("data-index");
            },
            handleDeactivatedRow: function(userId) {
                this.updateFieldData(userId, {index:this.getRowIndex(userId), field: "activationstatus", value: "deactivated", reinit: true});
                this.handleDeactivatedRowVis(userId);
            },
            handleDeactivatedRowVis: function(userId) {
                if (!userId) {
                    return false;
                }
                $("#" + this.ROW_ID_PREFIX + userId).addClass("deleted-user-row").addClass("rowlink-skip")
                .find(".deleted-button-cell").html('<span class="text-display">{inactivetext}</span><i data-user-id="{userid}" aria-hidden="true" title="Reactivate account" class="fa fa-undo reactivate-icon"></i>'.replace("{userid}", userId).replace("{inactivetext}", i18next.t("Inactive")))
                .find("a.profile-link").remove();
                if (!this.showDeletedUsers) {
                	$("#" + this.ROW_ID_PREFIX + userId).hide();
                }
            },
            handleReactivatedRow: function(userId) {
                if (!userId) {
                    return false;
                }
                this.updateFieldData(userId, {index:this.getRowIndex(userId), field: "activationstatus", value: "activated", reinit: true});
                this.handleReactivatedRowVis(userId);
            },
            handleReactivatedRowVis: function(userId) {
                if (!userId) {
                    return false;
                }
                $("#data_row_" + userId).removeClass("deleted-user-row").removeClass("rowlink-skip")
                .find(".deleted-button-cell")
                .html('<button id="btnDeleted{userid}" data-user-id="{userid}" type="button" class="btn btn-default btn-delete-user" data-original-title="" title=""><em>{buttontext}</em></button>'.replace(/\{userid\}/g, userId).replace("{buttontext}", i18next.t("Deactivate")))
                .append("<a class='profile-link'></a>");
                if (this.showDeletedUsers) {
                	$("#"+ this.ROW_ID_PREFIX + userId).hide();
                }
            }
        }
    });
})();
