<template>
    <main id="mainPsaApp">
        <section class="psa-tracker-title">
            <h2 class="tnth-header heading">{{intro.header}}</h2>
            <div class="body">{{intro.body}}</div>
            <div id="psaTrackerButtonsContainer"><button id="psaTrackerBtnAddNew" class="btn btn-tnth-primary" data-toggle="modal" data-target="#addPSAModal">{{intro.addText}}</button></div>
        </section>
        <section>
            <div id="psaTrackerNoResultContainer" class="text-warning" v-if="!items.length">
                {{noResultMessage}}
                <span v-if="isActedOn()">
                    <refresh-icon v-on:refresh="refresh" v-bind:title="getRefreshMessage()"></refresh-icon>
                </span>
            </div>
            <div id="psaTrackerResultsContainer" v-if="items.length > 0">
                <div class="psaTrackerLoader" v-bind:class="{ 'tnth-hide': !loading }"><i class="fa fa-spinner fa-spin fa-2x"></i></div>
                <div class="psaTrackerDataContainer" v-bind:class="{ 'tnth-hide': loading }">
                    <table id="psaTrackerResultsTable" >
                        <THEAD class="psa-tracker-table-header">
                            <th v-for="(item, index) in headers" :key="index">{{item}}</th>
                        </THEAD>
                        <TBODY>
                            <tr v-if="showFilters()" class="filter-row">
                                <td class="filter-cell">
                                    <filter-control v-bind:id="'psaTrackerYearFilter'" v-bind:prompt="filters.filterYearPrompt" v-bind:items="yearList" v-bind:selectedvalue="filters.selectedFilterYearValue" v-on:changeevent="filterDataByYearEvent"></filter-control>
                                </td>
                                <td class="filter-cell">
                                    <filter-control v-bind:id="'psaTrackerResultFilter'" v-bind:prompt="filters.filterResultPrompt" v-bind:items="resultRange" v-bind:selectedvalue="filters.selectedFilterResultRange" v-on:changeevent="filterDataByResultEvent"></filter-control>
                                </td>
                            </tr>
                            <tr v-for="item in items" v-bind:data-id="item.id" v-bind:data-date="item.date" :key="item.id" class="result-row" v-on:click="onEdit(item)">
                                <td class="result-cell"><div class="glyphicon glyphicon-pencil edit-icon" aria-hidden="true"></div><span>{{item.date}}</span></td>
                                <td class="result-cell"><span>{{item.result}}</span></td>
                            </tr>
                        </TBODY>
                        <TFOOT>
                            <tr>
                                <td colspan="2">
                                    <span class="glyphicon glyphicon-remove edit-icon" aria-hidden="true" v-on:click="refresh" v-bind:disabled="!isActedOn()" v-if="showFilters()" v-bind:title="filterText"></span>
                                    <a class="info-link" v-on:click="refresh" v-bind:disabled="!isActedOn()" v-if="showFilters()" v-html="filters.clearLabel" v-bind:title="filterText"></a>
                                </td>
                            </tr>
                        </TFOOT>
                    </table>
                    <div id="psaTrackerDataSidebar" v-show="history.items.length">
                        <button class="btn btn-tnth-primary" v-show="history.items.length" v-on:click="showHistory" v-html="history.buttonLabel"></button>
                    </div>
                </div>
                <div id="psaTrackerGraphContainer" v-bind:class="{ 'tnth-hide': loading }">
                    <div id="psaTrackerGraph"></div>
                    <div id="psaTrackerTreatmentContainer">
                        <div class="group" v-if="showTreatment()" v-for="(item, index) in treatment.data" :key="index">
                            <div>
                                <div class="title">{{treatment.treatmentTextPrompt}}</div><div class="content display-text">{{item.display}}</div>
                            </div>
                            <div>
                                <div class="title">{{treatment.treatmentDatePrompt}}</div> <div class="content display-text">{{item.date}}</div>
                            </div>
                        </div>
                        <div v-if="!showTreatment()">
                            <span class="text-warning" v-html="treatment.noTreatmentText"></span>
                        </div>
                        <div class="shift-right">
                            <a v-bind:href="treatmentEditUrl" class="info-link" v-html="editLink" v-bind:title="editText"></a>
                            <a v-bind:href="treatmentEditUrl" v-bind:title="editText"><span class="glyphicon glyphicon-pencil edit-icon" aria-hidden="true"></span></a>
                        </div>
                    </div>
                </div>
            </div>
            <div id="psaTrackerErrorMessageContainer" class="error-message"></div>
        </section>
        <div class="modal fade" id="addPSAModal" tabindex="-1" role="dialog">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal" v-bind:aria-label="closeText"><span aria-hidden="true">&times;</span></button>
                        <div class="modal-header-title" v-html="getAddModalTitle()"></div>
                    </div>
                    <div class="modal-body">
                        <div class="body-content">
                            <div class="psaTrackerModalLoader" v-bind:class="{ 'tnth-hide': !modalLoading }"><i class="fa fa-spinner fa-spin fa-2x"></i></div>
                            <table id="psaTrackerAddTable" v-bind:class="{ 'tnth-hide': modalLoading }">
                                <tr>
                                    <td class="field-label" v-html="fields.resultLabel"></td>
                                    <td><input id="psaResult" type="text" v-model.trim="newItem.result" class="form-control" v-bind:placeholder="fields.resultPlaceholder" /></td>
                                </tr>
                                <tr>
                                    <td class="field-label" v-html="fields.dateLabel"></td>
                                    <td><input id="psaDate" type="text" v-model.trim="newItem.date" class="form-control" v-bind:placeholder="fields.datePlaceholder" /></td>
                                </tr>
                            </table>
                            <br/>
                            <div class="error-message text-center" v-html="addErrorMessage"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <div v-bind:class="{'tnth-hide':!savingInProgress}"><i class="fa fa-spinner fa-spin fa-2x"></i></div>
                        <div v-bind:class="{'tnth-hide': savingInProgress}">
                            <button type="button" class="btn btn-default" v-on:click="onAdd()" v-bind:disabled="!isValidData()" v-html="saveText"></button>
                            <button type="button" class="btn btn-default" data-dismiss="modal" v-html="closeText"></button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="modal fade" id="PSAHistoryModal" tabindex="-1" role="dialog">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal" v-bind:aria-label="closeText"><span aria-hidden="true">&times;</span></button>
                    <div class="modal-header-title" v-html="history.title"></div>
                </div>
                <div class="modal-body">
                    <div class="body-content">
                        <table id="psaTrackerHistoryTable">
                            <THEAD class="psa-tracker-table-header"><TH v-for="(item, index) in headers" v-html="item" :key="index">{{item}}</TH></THEAD>
                            <TR v-for="(item,index) in history.items" :key="index"><TD v-html="item.date"></TD><TD v-html="item.result"></TD></TR>
                        </table>
                        <div class="text-warning sidenote" v-html="history.sidenote"></div>
                    </div>
                </div>
                <div class="modal-footer"><button type="button" class="btn btn-default" data-dismiss="modal" v-html="closeText"></button></div>
                </div>
            </div>
        </div>
        <svg width="300" height="200">
            <defs>
                <path id="arrow" d="M2,2 L10,6 L2,10 L6,6 L2,2" class="marker" transform="rotate(90)" stroke-width="4"></path>
                <rect id="marker" width="4" height="4" stroke-width="1" class="marker"></rect>
            </defs>
        </svg>
    </main>
</template>
<script>
    import FilterControl from "./FilterControl.vue";
    import RefreshIcon from "./RefreshIcon.vue";
    import tnthAjax from "../modules/TnthAjax.js";
    import tnthDates from "../modules/TnthDate.js";
    import SYSTEM_IDENTIFIER_ENUM from "../modules/SYSTEM_IDENTIFIER_ENUM.js";
    export default {
        components: { RefreshIcon, FilterControl},
        errorCaptured: function(Error, Component, info) { /*eslint no-console: off */
            console.error("Error: ", Error, " Component: ", Component, " Message: ", info);
            return false;
        },
        errorHandler: function(err, vm) {
            this.dataError = true;
            var errorElement = document.getElementById("psaTrackerErrorMessageContainer");
            if(errorElement) {
                errorElement.innerHTML = "Error occurred initializing PSA Tracker Vue instance.";
            }
            if (window.console) {
                console.warn("PSA Tracker Vue instance threw an error: ", vm, this);
                console.error("Error thrown: ", err); /*console global */
            }
        },
        created: function() {
            if (typeof Vue === "undefined") { return false; } /*global Vue */
            var self = this;
            Vue.config.errorHandler = function (err, vm, info)  {
                var handler, current = vm;
                if (vm.$options.errorHandler) {
                    handler = vm.$options.errorHandler;
                } else {
                    while (!handler && current.$parent) {
                        current = current.$parent;
                        handler = current.$options.errorHandler;
                    }
                }
                self.restoreVis();
                if (handler) {
                    handler.call(current, err, vm, info);
                    return;
                }
                console.log(err);
            };
        },
        mounted: function() {
            var self = this;
            $(function() { /*global $ tnthDates, tnthAjax, SYSTEM_IDENTIFIER_ENUM, i18next, d3 */
                self.init({ tnthDates: tnthDates, tnthAjax: tnthAjax, SYSTEM_IDENTIFIER_ENUM: SYSTEM_IDENTIFIER_ENUM, d3: d3});
            });
        },
        data: function() {
            return {
                userId: "",
                userIdKey: "psaTracker_currentUser",
                clinicalCode: "666",
                clinicalDisplay: "psa",
                clinicalSystem: "http://us.truenth.org/clinical-codes",
                loading: false,
                savingInProgress: false,
                addErrorMessage: "",
                noResultMessage: i18next.t("No PSA results to display"),
                editText: i18next.t("Edit"),
                saveText: i18next.t("Save"),
                closeText: i18next.t("Close"),
                filterText: i18next.t("Filter"),
                yLegendText: i18next.t("Result (ng/ml)"),
                xLegendText: i18next.t("PSA Test Date"),
                MAX_RESULT: 10000,
                treatmentEditUrl: "profile#profileProceduresWrapper",
                newItem: {
                    id: "",
                    result: "",
                    date: "",
                    edit: false
                },
                headers: [
                    i18next.t("Date"),
                    i18next.t("PSA (ng/ml)")
                ],
                intro: {
                    header: i18next.t("Track Your PSA"),
                    body: i18next.t("Prostate-specific antigen, or PSA, is a protein produced by cells of the prostate gland. The PSA test measures the level of PSA in a man's blood. For this test, a blood sample is sent to a laboratory for analysis. The results are reported as nanograms of PSA per milliliter (ng/mL) of blood."),
                    addText: i18next.t("ADD NEW PSA RESULT")
                },
                fields: {
                    resultLabel: i18next.t("PSA (ng/ml)"),
                    dateLabel: i18next.t("PSA Test Date"),
                    resultPlaceholder: i18next.t("Enter a number"),
                    datePlaceholder: i18next.t("d M yyyy, example: 1 Jan, 2017")
                },
                items: [],
                history: {
                    title: i18next.t("PSA Result History"),
                    items: [],
                    buttonLabel: i18next.t("History"),
                    sidenote: ""
                },
                originals: [],
                resultRange: ["<= 4", ">= 2", ">= 3", ">= 4", ">= 5"],
                RANGE_ENUM: {
                    "<= 4": function(items) { return $.grep(items, function(item) {
                        return item.result <= 4;
                    });},
                    ">= 2": function(items) { return $.grep(items, function(item) {
                        return item.result >= 2;
                    });},
                    ">= 3": function(items) { return $.grep(items, function(item) {
                        return item.result >= 3;
                    });},
                    ">= 4": function(items) { return $.grep(items, function(item) {
                        return item.result >= 4;
                    });},
                    ">= 5": function(items) { return $.grep(items, function(item) {
                        return item.result >= 5;
                    });}
                },
                filters: {
                    filterYearPrompt: i18next.t("Filter By Year"),
                    filterResultPrompt: i18next.t("Filter By Result"),
                    selectedFilterYearValue: "",
                    selectedFilterResultRange: "",
                    clearLabel: i18next.t("Clear Filters")
                },
                showRefresh: false,
                treatment: {
                    treatmentTextPrompt: i18next.t("Last Received Treatment:"),
                    treatmentDatePrompt: i18next.t("Treatment Date:"),
                    noTreatmentText: i18next.t("No treatment received as of today"),
                    data: []
                },
                modalLoading: false,
                editLink: i18next.t("Edit"),
                editTitle: i18next.t("Edit PSA Result"),
                addTitle: i18next.t("Add PSA Result")
            };
        },
        computed: {
            yearList: function() {
                var yearList = this.originals.map(function(item) {
                    return item.titleYear;
                });
                yearList = $.grep(yearList, function(item, index) {
                    return yearList.indexOf(item) === index;
                });
                return yearList;
            }
        },
        methods: {
            init: function(dependencies) {
                var self = this;
                dependencies = dependencies || {};
                for(var prop in dependencies) {
                    if (dependencies.hasOwnProperty(prop)) {
                        self[prop] = dependencies[prop];
                    }
                }
                sessionStorage.removeItem(this.userIdKey);
                this.getData(true);
                this.getProcedure();
                setTimeout(function() {
                    self.initElementsEvents();
                }, 300);
            },
            isActedOn: function() {
                return this.showRefresh && (this.filters.selectedFilterYearValue !== "" || this.filters.selectedFilterResultRange !== "");
            },
            restoreVis: function() {
                var loadingElement = document.getElementById("loadingIndicator"), mainElement = document.getElementById("mainHolder");
                if (loadingElement) { loadingElement.setAttribute("style", "display:none; visibility:hidden;"); }
                if (mainElement) { mainElement.setAttribute("style", "visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1"); }
            },
            isEdit: function() {
                return this.newItem.edit;
            },
            refresh: function() {
                this.clearFilter();
                this.getData();
            },
            getAddModalTitle: function() {
                if (this.newItem.edit) {
                    return this.editTitle;
                }
                return this.addTitle;
            },
            getRefreshMessage: function() {
                return i18next.t("Click to reload the page and try again.");
            },
            validateResult: function(val) {
                var isValid = !(isNaN(val) || parseInt(val) < 0 || parseInt(val) > this.MAX_RESULT);
                if(!isValid) {
                    this.addErrorMessage = i18next.t("Result must be a number and within valid range (less than {max_result}).").replace("{max_result}", this.MAX_RESULT);
                    return false;
                }
                this.addErrorMessage = "";
                return isValid;
            },
            validateDate: function(date) {
                if (!date || date.length <= 9) { //don't show validation error until enough characters are entered, just return false
                    return false;
                }
                var isValid = this.tnthDates.isValidDefaultDateFormat(date);
                if(!isValid) {
                    this.addErrorMessage = i18next.t("Date must be in the valid format.");
                } else {
                    this.addErrorMessage = "";
                }
                return isValid;
            },
            formatDateString: function(date, format) {
                return this.tnthDates.formatDateString(date, format);
            },
            initElementsEvents: function() {
                var self = this;
                /*
                 * date picker events
                 */
                $("#psaDate").datepicker({
                    "format": "d M yyyy",
                    "forceParse": false,
                    "endDate": new Date(),
                    "maxViewMode": 2,
                    "autoclose": true
                }).on("hide", function() {
                    $("#psaDate").trigger("blur");
                });
                $("#psaDate").on("change blur", function() {
                    var newDate = $(this).val();
                    if (!newDate || !self.validateDate(newDate)) {
                        return false;
                    }
                    self.newItem.date = newDate;
                }).on("focus", function() {
                    self.modalLoading = false;
                });
                /*
                 * new result field event
                 */
                $("#psaResult").on("blur", function() {
                    self.validateResult($(this).val());
                });

                $("#psaTrackerBtnAddNew").on("click", function() {
                    self.clearNew();
                });
                /*
                 * use numeric keypad for PSA result on mobile devices
                 */
                 this.convertToNumericField($("#psaResult"));
                /*
                 * modal event
                 */
                $("#addPSAModal").on("show.bs.modal", function() {
                    self.modalLoading = true;
                });
                $("#addPSAModal").on("shown.bs.modal", function() {
                    $("#psaResult").focus();
                    $("#psaDate").datepicker("update", self.newItem.date||new Date());
                    setTimeout(function() {
                        self.modalLoading = false; //allow time for setting value with it being visible to user
                    }, 50);
                });
                $("#psaTrackerResultsTable .result-row").on("mouseover", function() {
                    $(this).addClass("edit");
                }).on("mouseout", function() {
                    $(this).removeClass("edit");
                });
            },
            convertToNumericField: function(field) {
                if (field && ("ontouchstart" in window || (typeof(window.DocumentTouch) !== "undefined" && document instanceof window.DocumentTouch))) {
                    field.each(function() {$(this).prop("type", "tel");});
                }
            },
            getCurrentUserId: function() {
                var self = this;
                if(!sessionStorage.getItem(this.userIdKey)) {
                    this.tnthAjax.sendRequest("/api/me", "GET", "", { sync: true }, function(data) {
                        if(!data.error) {
                            sessionStorage.setItem(self.userIdKey, data.id);
                        } else {
                            sessionStorage.setItem(self.userIdKey, $("#psaTracker_currentUser").val());
                        }
                    });
                }
                return sessionStorage.getItem(this.userIdKey);
            },
            getExistingItemByDate: function(newDate) {
                var convertedDate = this.tnthDates.formatDateString(newDate, "iso-short"), self = this;
                return $.grep(this.items, function(item) {
                    return convertedDate === self.tnthDates.formatDateString(item.date, "iso-short");
                });
            },
            onEdit: function(item) {
                var self = this;
                if(item) {
                    for(var prop in self.newItem) {
                        if (self.newItem.hasOwnProperty(prop)) {
                            self.newItem[prop] = item[prop];
                        }
                    }
                    setTimeout(function() {
                        $("#addPSAModal").modal("show");
                    }, 250);
                }
            },
            isValidData: function() {
                var newDate = this.newItem.date;
                var newResult = this.newItem.result;
                return newDate && this.validateDate(newDate) && newResult && this.validateResult(newResult);
            },
            onAdd: function() {
                if (!this.isValidData()) {
                    return false;
                }
                this.addErrorMessage = "";
                var existingItem = this.getExistingItemByDate(this.newItem.date);
                if(existingItem.length > 0) {
                    this.newItem.id = existingItem[0].id;
                }
                this.postData();
            },
            getProcedure: function() {
                var self = this;
                this.tnthAjax.getProc(this.getCurrentUserId(), false, function(data) {
                    if (!data) { return false; }
                    data.entry = data.entry || [];
                    var treatmentData = $.grep(data.entry, function(item) {
                        var code = item.resource.code.coding[0].code;
                        return code !== SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE && code !== SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE;
                    });
                    if (treatmentData.length === 0) { return false; }
                    treatmentData.sort(function(a, b) {
                        return new Date(b.resource.performedDateTime) - new Date(a.resource.performedDateTime);
                    });
                    self.treatment.data = [treatmentData.map(function(item) {
                        return {
                            "display": item.resource.code.coding[0].display,
                            "date": self.formatDateString(item.resource.performedDateTime.substring(0, 19), "d M y")
                        };
                    })[0]];
                });
            },
            showTreatment: function() {
                return this.treatment.data.length > 0;
            },
            getData: function() {
                var self = this;
                this.loading = true;
                this.tnthAjax.getClinical(this.getCurrentUserId(), {data: {patch_dstu2: true}}, function(data) {
                    if(data.error) {
                        $("#psaTrackerErrorMessageContainer").html(i18next.t("Error occurred retrieving PSA result data"));
                        self.loading = false;
                        return false;
                    }
                    if (!data.entry) {
                        $("#psaTrackerErrorMessageContainer").html(i18next.t("No result data found"));
                        self.loading = false;
                        return false;
                    }
                    var results = (data.entry).map(function(item) {
                        var dataObj = {}, content = item.resource, contentCoding = content.code.coding[0];
                        item.updated = item.updated || "";
                        dataObj.id = content.id;
                        dataObj.code = contentCoding.code;
                        dataObj.display = contentCoding.display;
                        dataObj.updated = self.formatDateString(item.updated.substring(0, 19), "yyyy-mm-dd hh:mm:ss");
                        dataObj.date = content.issued ? self.formatDateString(content.issued.substring(0, 19), "d M y"): "";
                        dataObj.result = content.valueQuantity.value;
                        dataObj.edit = true;
                        dataObj.titleYear = new Date(content.issued).getFullYear();
                        return dataObj;
                    });
                    results = $.grep(results, function(item) {
                        return item.display.toLowerCase() === "psa";
                    });
                    // sort from newest to oldest
                    results = results.sort(function(a, b) {
                        return new Date(b.date) - new Date(a.date);
                    });
                    /*
                     * display only 10 most recent results
                     */
                    if(results.length > 10) {
                        var tempResults = results;
                        results = results.slice(0, 10);
                        self.history.items = tempResults.slice(10, 20);
                        self.history.sidenote = String(i18next.t("* Maximum of {resultNumber} results since {year}")).replace("{resultNumber}", 10).replace("{year}", self.getHistoryMinYear());
                    }
                    if (results.length === 0) {
                        self.noResultMessage = i18next.t("No PSA results to display");
                    }
                    self.items = self.originals = results;
                    self.filterData();
                    setTimeout(function() {
                        self.drawGraph();
                        self.loading = false;
                    }, 500);
                    $("#psaTrackerErrorMessageContainer").html("");
                });
            },
            showHistory: function() {
                $("#PSAHistoryModal").modal("show");
            },
            getHistoryMinYear: function() {
                if (this.history.items.length === 0) {
                    return false;
                }
                var yearArray = this.history.items.map(function(item) {
                    return (new Date(item.date)).getFullYear();
                });
                yearArray.sort(function(a, b) {
                    return a - b;
                });
                return yearArray[0];
            },
            clearFilter: function() {
                this.filters.selectedFilterResultRange = "";
                this.filters.selectedFilterYearValue = "";
            },
            filterData: function(redraw) {
                var results = this.originals, self = this;
                this.items = this.originals;
                if (this.filters.selectedFilterYearValue !== "") {
                    results = $.grep(results, function(item) {
                        return parseInt(item.titleYear) === parseInt(self.filters.selectedFilterYearValue);
                    });
                    this.items = results;
                }
                if (this.filters.selectedFilterResultRange) {
                    this.items = this.RANGE_ENUM[this.filters.selectedFilterResultRange](this.items);
                }
                if (this.items.length === 0 && this.isActedOn()) {
                    this.noResultMessage = i18next.t("No PSA result matching the filtering criteria. Please try again.");
                }
                if (!redraw) {
                    return false;
                }
                setTimeout(function() {
                    self.drawGraph();
                }, 500);
            },
            filterDataByYearEvent: function(event) {
                this.showRefresh = true;
                this.filters.selectedFilterYearValue = event.target.value;
                this.filterData(true);
            },
            filterDataByResultEvent: function(event) {
                this.showRefresh = true;
                this.filters.selectedFilterResultRange = event.target.value;
                this.filterData(true);
            },
            showFilters: function() {
                return this.originals.length > 1;
            },
            postData: function() {
                var cDate = "";
                var self = this;
                var userId = this.getCurrentUserId();
                if(this.newItem.date) {
                    var dt = new Date(this.newItem.date);
                    // in 2017-07-06T12:00:00 format
                    cDate = [dt.getFullYear(), (dt.getMonth() + 1), dt.getDate()].join("-");
                    cDate = cDate + "T12:00:00";
                }
                var url = "/api/patient/" + userId + "/clinical";
                var method = "POST";
                var obsCode = [{ "code": this.clinicalCode, "display": this.clinicalDisplay, "system": this.clinicalSystem }];
                var obsArray = {};
                obsArray["resourceType"] = "Observation";
                obsArray["code"] = { "coding": obsCode };
                obsArray["issued"] = cDate;
                obsArray["valueQuantity"] = { "units": "g/dl", "code": "g/dl", "value": this.newItem.result };

                if(this.newItem.id) {
                    method = "PUT";
                    url = url + "/" + this.newItem.id;
                }
                this.savingInProgress = true;
                this.tnthAjax.sendRequest(url, method, userId, { data: JSON.stringify(obsArray), async: true }, function(data) {
                    if(data.error) {
                        self.addErrorMessage = i18next.t("Server error occurred adding PSA result.");
                    } else {
                        $("#addPSAModal").modal("hide");
                        self.clearFilter(); //clear filter after every new data update?
                        self.getData();
                        self.addErrorMessage = "";
                    }
                    setTimeout(function() {
                        self.savingInProgress = false;
                    }, 550);
                });
            },
            clearNew: function() {
                var self = this;
                for(var prop in self.newItem) {
                    if (self.newItem.hasOwnProperty(prop)) {
                        self.newItem[prop] = "";
                    }
                }
                $("#psaDate").datepicker("update", "");
            },
            __handleTreatmentDate: function(minDate, maxDate, step) { //use internally
                if (this.treatment.data.length === 0) {
                    return false;
                }
                step = Math.floor(step/2); //should throw error if no value provided
                var treatmentDate = new Date(this.treatment.data[0].date);
                if (treatmentDate.getTime() < minDate.getTime()) {
                    var startMinDate = new Date(minDate);
                    return new Date(startMinDate.setUTCDate(startMinDate.getUTCDate() - step));
                }
                if (treatmentDate.getTime() > maxDate.getTime()) {
                    var startMaxDate = new Date(maxDate);
                    return new Date(startMaxDate.setUTCDate(startMaxDate.getUTCDate() + step));
                }
                return treatmentDate;
            },
            getNearestPow10: function(n){ //find the closest power of 10 given a number
                var base = Math.log(n) / Math.LN10;
                if (base >= Math.ceil(base)-0.1) {
                    base = base + 1; //accounting for when log of number is perfect integer, 1, 10, 100, 1000, so need to draw next grid line up
                }
                else {
                    base = Math.ceil(base);
                }
                return Math.pow(10, base);
            },
            getRange: function getRange(size, startAt, step) {
                var arr = []; size=size||10; startAt=startAt||0; step = step||1;
                for (var index=startAt; index < size; index++) {
                    arr.push(step*index);
                }
                return arr;
            },
            getDayInMiliseconds: function() {
                return 1000 * 60 * 60 * 24;
            },
            getInterval: function(minDate, maxDate, step) {
                step = step || 8;
                if (!maxDate || !minDate) {
                    return step;
                }
                var DAY = this.getDayInMiliseconds();
                var DIFF = (new Date(maxDate) - new Date(minDate)) / DAY;
                return Math.ceil(DIFF / step);
            },
            dateTicks: function(t0, t1) {
                var startTime = new Date(t0), endTime = new Date(t1), times = [], dateTime;
                var INTERVAL = this.getInterval(t0, t1, 7) || 7;
                startTime.setUTCDate(startTime.getUTCDate());
                endTime.setUTCDate(endTime.getUTCDate());
                while(startTime <= endTime) {
                    dateTime = new Date(startTime);
                    startTime.setUTCDate(startTime.getUTCDate() + INTERVAL);
                    times.push(dateTime);
                    if (startTime > endTime) {
                        times.push(new Date(endTime));
                    }
                }
                return times;
            },
            setLetterSpacing: function(string) {
                string = string || "";
                var dxString = "0 ";
                for (var index = 1; index < string.length; index++) {
                    if (/\s/.test(string.charAt(index))) {
                        dxString += "3 ";
                        continue;
                    }
                    dxString += "2 ";
                }
                return dxString;
            },
            drawGraph: function() { //using d3 library to draw graph
                $("#psaTrackerGraph").html("");
                var self = this;
                var d3 = self.d3;
                var WIDTH = 640, HEIGHT = 430, TOP = 50, RIGHT = 40, BOTTOM = 70, LEFT = 70, TIME_FORMAT = "%d %b %Y";

                // Set the dimensions of the canvas / graph
                var margin = { top: TOP, right: RIGHT, bottom: BOTTOM, left: LEFT },
                    width = WIDTH - margin.left - margin.right,
                    height = HEIGHT - margin.top - margin.bottom;

                var timeFormat = d3.time.format(TIME_FORMAT);
                var parseDate = timeFormat.parse; // Parse the date / time func
                var data = self.items;

                data.forEach(function(d) {
                    d.graph_date = parseDate(d.date);
                    d.result = isNaN(d.result) ? 0.1 : +d.result;
                });

                var minDate = d3.min(data, function(d) {
                    return d.graph_date;
                });
                var maxDate = d3.max(data, function(d) {
                    return d.graph_date;
                });
                var maxResult = d3.max(data, function(d) {
                    return d.result;
                });

                var xDomain = d3.extent(data, function(d) { return d.graph_date; });
                var bound = (width - margin.left - margin.right) / 7;
                var x = d3.time.scale().range([bound, width - bound]);
                var y = d3.scale.log().range([height, 0]); //log scale

                if (data.length <= 2 || String(minDate) === String(maxDate)) {
                    var firstDate = new Date(maxDate);
                    maxDate = new Date(firstDate.setDate(firstDate.getDate() + 365));
                    xDomain = [minDate, maxDate];
                }

                var maxResultInLog = self.getNearestPow10(maxResult);

                x.domain(xDomain);
                y.domain([0.1, maxResultInLog]); //scale to the closest power of 10 based on the maximum result
                // Define the axes
                var xAxis = d3.svg.axis()
                    .scale(x)
                    .orient("bottom")
                    .ticks(self.dateTicks)
                    .tickSize(0, 0, 0)
                    .tickFormat(timeFormat);

                var yAxis = d3.svg.axis()
                    .scale(y)
                    .ticks(10)
                    .orient("left")
                    .tickSize(0, 0, 0);

                // Define the line
                var valueline = d3.svg.line()
                    .x(function(d) { return x(d.graph_date); })
                    .y(function(d) { return y(d.result); });

                // Adds the svg canvas
                var svg = d3.select("#psaTrackerGraph")
                    .append("svg")
                    .attr("width", width + margin.left + margin.right)
                    .attr("height", height + margin.top + margin.bottom);

                var graphArea = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");

                // Add the X Axis
                graphArea.append("g")
                    .attr("class", "x axis x-axis")
                    .attr("transform", "translate(0," + (height +  5) + ")")
                    .call(xAxis)
                    .selectAll("text")
                    .call(function(text) {
                        text.each(function() {
                            var textNode = d3.select(this);
                            var dateString = textNode.text();
                            var arrDate = dateString.split(/\s+/);
                            var dx = "-1.25em";
                            textNode.text(null).append("tspan").attr("x", 0).attr("y", textNode.attr("y")).attr("dx", dx).attr("dy", textNode.attr("dy")).text(arrDate[0] + " " + arrDate[1]);
                            textNode.append("tspan").attr("x", 0).attr("y", textNode.attr("y")).attr("dx", "-1em").attr("dy", "2em").text(arrDate[2]);
                        });
                    })
                    .attr("y", 0)
                    .attr("x", 7)
                    .attr("dy", ".35em")
                    .attr("class", "axis-stroke")
                    .style("letter-spacing", "1px")
                    .style("text-anchor", "start");

                // add the X gridlines
                graphArea.append("g")
                    .attr("class", "grid grid-x")
                    .attr("transform", "translate(0," + height + ")")
                    .call(xAxis
                        .tickSize(-height, 0, 0)
                        .tickFormat("")
                    );
                // add the Y ticks and gridlines
                graphArea.append("g")
                    .attr("class", "grid grid-y")
                    .call(yAxis
                        .tickSize(-width, 0, 0)
                        .tickValues(function() {
                            return self.getRange(Math.log(maxResultInLog),-1,0.5).map(function(n) { //finer lines between each log base 10 line
                                return Math.pow(10, n); //draw grid in log scale
                            });
                        })
                        .tickFormat(function(d) {
                            if (d === parseInt(d)) { //this will only show tick values that are integers
                                return d;
                            }
                            return "";
                        })
                    )
                    .selectAll("text")
                    .attr("dx", "-2px")
                    .attr("dy", "6px")
                    .attr("class", "axis-stroke")
                    .style("text-anchor", "end");

                //borders around graph area
                var BORDER_STROKE_COLOR = "#3F4B54";
                svg.append("path").attr("d", "M " + margin.left + " " + margin.top + " V " + (HEIGHT-margin.bottom) + " H" + (WIDTH-margin.right))
                    .style("stroke", BORDER_STROKE_COLOR)
                    .style("stroke-width", "1");
                svg.append("path").attr("d", "M " + margin.left + " " + margin.top + " H " + (WIDTH-margin.right) + " V " + (HEIGHT-margin.bottom))
                    .style("stroke", BORDER_STROKE_COLOR)
                    .style("stroke-width", "0.5");

                //add div for tooltip
                var tooltipContainer = d3.select("body").append("div").attr("class", "tooltip").style("opacity", 0);

                //treatment line
                var treatmentDate = self.__handleTreatmentDate(minDate, maxDate, self.getInterval(minDate, maxDate, 7));
                var TREATMENT_TEXT_COLOR = "#EF425C";
                if (treatmentDate) {
                    var treatmentPath = graphArea.append("path");
                    treatmentPath.attr("d", "M"+x(treatmentDate) + " 0" + " V " + height + " Z")
                        .style("stroke", TREATMENT_TEXT_COLOR)
                        .style("stroke-dasharray", "1, 5")
                        .style("stroke-width", "2");

                    graphArea.append("use")
                        .attr("x", x(treatmentDate) - 2)
                        .attr("y", -2)
                        .attr("xlink:href", "#marker");

                    graphArea.append("use")
                        .attr("x", x(treatmentDate) + 6)
                        .attr("y", height - 6)
                        .attr("xlink:href", "#arrow");

                    var RECT_HEIGHT = 25, RECT_WIDTH = 76;
                    graphArea.append("rect")
                        .attr("x", x(treatmentDate) - RECT_WIDTH/2)
                        .attr("y", 25)
                        .attr("width", RECT_WIDTH)
                        .attr("height", RECT_HEIGHT)
                        .style("stroke", TREATMENT_TEXT_COLOR)
                        .style("stroke-width", "0.5")
                        .style("fill", TREATMENT_TEXT_COLOR);
                    graphArea.append("text")
                        .attr("x", x(treatmentDate))
                        .attr("y", 41)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "11px")
                        .style("stroke-width", "4px")
                        .style("fill", "#FFF")
                        .style("letter-spacing", "2px")
                        .text(i18next.t("treatment"));
                }

                // Add the valueline path.
                graphArea.append("path")
                    .attr("class", "line")
                    .style("stroke", "#bec0c1")
                    .style("stroke-width", 2)
                    .attr("d", valueline(data));

                // Add the scatterplot
                var circleRadius = 7.7, CIRCLE_STROKE_COLOR = "#809EAE";
                graphArea.selectAll("circle").data(data)
                    .enter().append("circle")
                    .transition()
                    .duration(850)
                    .delay(function(d, i) { return i * 7; })
                    .style("stroke", CIRCLE_STROKE_COLOR)
                    .style("stroke-width", 2)
                    .attr("r", circleRadius)
                    .attr("class", "circle")
                    .attr("cx", function(d) { return x(d.graph_date); })
                    .attr("cy", function(d) { return y(d.result); });
                graphArea.selectAll("circle")
                    .on("mouseover", function(d) {
                        var element = d3.select(this);
                        element.transition().duration(100).attr("r", circleRadius * 1.2);
                        element.style("fill", CIRCLE_STROKE_COLOR)
                            .classed("focused", true);
                        var TOOLTIP_WIDTH = (String(d.date).length*8 + 10);
                        tooltipContainer.transition().duration(200).style("opacity", .9); //show tooltip for each data point
                        tooltipContainer.html("<b>" + i18next.t("PSA") + "</b> " + d.result + "<br/><span class='small-text'>" + d.date + "</span>")
                            .style("width", TOOLTIP_WIDTH + "px")
                            .style("height", 35 + "px")
                            .style("left", (d3.event.pageX - TOOLTIP_WIDTH/2) + "px")
                            .style("top", (d3.event.pageY - TOOLTIP_WIDTH/2) + "px");
                    })
                    .on("mouseout", function() {
                        var element = d3.select(this);
                        element.transition()
                            .duration(100)
                            .attr("r", circleRadius);
                        element.style("stroke", CIRCLE_STROKE_COLOR)
                            .style("fill", "#FFF")
                            .classed("focused", false);
                        tooltipContainer.transition().duration(500).style("opacity", 0);
                    });

                // Add text labels
                graphArea.selectAll("text.text-label")
                    .data(data)
                    .enter()
                    .append("text")
                    .classed("text-label", true)
                    .attr("x", function(d) {
                        return x(d.graph_date);
                    })
                    .attr("y", function(d) {
                        return y(d.result);
                    })
                    .attr("text-anchor", "middle")
                    .attr("dy", "-1.35em")
                    .attr("font-size", "11px")
                    .style("stroke-width", "2")
                    .attr("font-weight", "500")
                    .attr("letter-spacing", "2px")
                    .attr("fill", "#656F76")
                    .text(function(d) {
                        return d.result;
                    });

                // Add caption
                graphArea.append("text")
                    .attr("x", (width / 2))
                    .attr("y", 0 - (margin.top / 2))
                    .attr("text-anchor", "middle")
                    .attr("class", "graph-caption")
                    .text("PSA (ng/ml)");

                //add axis legends
                var xlegend = graphArea.append("g")
                    .attr("transform", "translate(" + (width / 2 - margin.left + margin.right - 20) + "," + (height + margin.bottom - margin.bottom / 5) + ")");

                xlegend.append("text")
                    .text(self.xLegendText)
                    .attr("dx", self.setLetterSpacing(self.xLegendText))
                    .attr("class", "legend-text");

                var ylegend = graphArea.append("g")
                    .attr("transform", "translate(" + (-margin.left + margin.left / 2 - 5) + "," + (height / 2 + height / 6) + ")");

                ylegend.append("text")
                    .attr("transform", "rotate(270)")
                    .attr("class", "legend-text")
                    .attr("dx", self.setLetterSpacing(self.yLegendText)) //using dx attribute for letter spacing due to FF not supporting SVG element's letter spacing styling
                    .text(self.yLegendText);

            }
        }
    };
</script>
