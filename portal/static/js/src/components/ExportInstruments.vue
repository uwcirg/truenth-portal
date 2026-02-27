<template>
    <div>
        <div class="modal fade" id="dataDownloadModal" tabindex="-1" role="dialog">
            <div class="modal-dialog modal-dialog-centered" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal" :aria-label="closeLabel"><span aria-hidden="true">&times;</span></button>
                        <span v-text="title"></span>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <!-- radio buttons selector for either main study or sub-study instruments -->
                            <div id="studyListSelector" class="list-selector sub-study">
                                <div class="items">
                                    <div class="item">
                                        <input type="radio" name="listSelector" @click="setCurrentMainStudy()" checked>
                                        <span class="text" v-text="mainStudySelectorLabel" :class="{'active': isCurrentMainStudy()}"></span>
                                    </div>
                                    <div class="item">
                                        <input type="radio" name="listSelector" @click="setCurrentSubStudy()">
                                        <span class="text" v-text="subStudySelectorLabel" :class="{'active': isCurrentSubStudy()}"></span>
                                    </div>
                                </div>
                            </div>
                            <label class="text-muted prompt" v-text="instrumentsPromptLabel"></label>
                            <div id="patientsInstrumentListWrapper">
                                <!-- dynamically load instruments list -->
                                <div id="patientsInstrumentList" class="profile-radio-list">
                                    <div v-show="isCurrentMainStudy()">
                                        <div class="list">
                                            <div class="checkbox instrument-container" :id="code+'_container'" v-for="code in mainStudyInstrumentsList"><label><input type="checkbox" name="instrument" :value="code">{{getDisplayInstrumentName(code)}}</label></div>
                                        </div>
                                    </div>
                                    <!-- sub-study instrument list, should only display when the user is part of the sub-study -->
                                    <div v-show="isCurrentSubStudy()">
                                        <div class="list">
                                            <div class="checkbox instrument-container" :id="code+'_container'" v-for="code in subStudyInstrumentsList"><label><input type="checkbox" name="instrument" :value="code">{{getDisplayInstrumentName(code)}}</label></div>
                                        </div>
                                    </div>
                                </div>
                                <div id="instrumentListLoad"><i class="fa fa-spinner fa-spin fa-2x loading-message"></i></div>
                            </div>
                        </div>
                        <div class="form-group data-types-container">
                            <label class="text-muted prompt" v-text="dataTypesPromptLabel"></label>
                            <div id="patientsDownloadTypeList" class="profile-radio-list">
                                <label class="radio-inline" v-for="item in dataTypes" :key="item.id" :class="{'active': item.value == 'csv'}">
                                    <input type="radio" name="downloadType" :id="item.id" :value="item.value" @click="setDataType" :checked="item.value == 'csv'" />
                                    {{item.label}}
                                </label>
                            </div>
                        </div>
                        <div id="instrumentsExportErrorMessage" class="error-message"></div>
                        <!-- display export status -->
                        <ExportDataLoader 
                            ref="exportDataLoader"
                            :initElementId="getInitElementId()"
                            :exportUrl="getExportUrl()"
                            :exportIdentifier="currentStudy"
                            v-on:initExport="handleInitExport"
                            v-on:doneExport="handleAfterExport"
                            v-on:initExportCustomEvent="initExportEvent"></ExportDataLoader>
                        <!-- display link to the last export -->
                        <div class="export__history" v-if="hasExportHistory()">
                            <div class="text-muted prompt" v-text="exportHistoryTitle"></div>
                            <div v-if="exportHistory">
                                <a :href="exportHistory.url" target="_blank">
                                    <span v-text="(exportHistory.instruments || []).join(', ')"></span>
                                    <span v-text="exportHistory.date"></span>
                                </a>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-default btn-emphasis" id="patientsDownloadButton" :disabled="!hasInstrumentsSelection()" v-text="exportLabel"></button>
                        <button type="button" class="btn btn-default" data-dismiss="modal" v-text="closeLabel"></button>
                    </div>
                </div>
            </div>
        </div>
        <div id="patientListExportDataContainer">
            <a href="#" id="patientAssessmentDownload"  class="btn btn-tnth-primary" data-toggle="modal" data-target="#dataDownloadModal"><span v-text="title" /></a>
        </div>
    </div>
</template>
<script>
    import Global from "../modules/Global.js";
    import tnthAjax from "../modules/TnthAjax.js";
    import CurrentUser from "../mixins/CurrentUser.js";
    import {EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER} from "../data/common/consts.js";
    import ExportInstrumentsData from "../data/common/ExportInstrumentsData.js";
    import ExportDataLoader from "./asyncExportDataLoader.vue";
    export default { /*global i18next */
        components: {ExportDataLoader},
        data: function() {
            return {...ExportInstrumentsData, ...{
                currentStudy: "main",
                mainStudyIdentifier: "main",
                subStudyIdentifier: "substudy",
                mainStudyInstrumentsList:[],
                subStudyInstrumentsList:[],
                exportHistory: null,
                currentTaskUrl: null
            }};
        },
        mixins: [CurrentUser],
        mounted: function() {
            this.setCurrentMainStudy();
            this.initCurrentUser(function() {
                this.getInstrumentList();
                this.handleSetExportHistory();
            }.bind(this));
        },
        watch: {
            currentStudy: function(newVal, oldVal) {
                //watch for when study changes
                //reset last exported item link as it is specific to each study
                this.handleSetExportHistory();
                //reset export display info
                this.resetExportInfoUI();
                //reset instrument(s) selected
                this.resetInstrumentSelections();
            },
        },
        methods: {
            getInitElementId: function() {
                return "patientsDownloadButton";
            },
            setCurrentStudy: function(identifier) {
                if (!identifier) return;
                this.currentStudy = identifier;
            },
            setCurrentMainStudy: function() {
                this.setCurrentStudy(this.mainStudyIdentifier);
            },
            setCurrentSubStudy: function() {
                this.setCurrentStudy(this.subStudyIdentifier);
            },
            isCurrentMainStudy: function() {
                return this.currentStudy === this.mainStudyIdentifier;
            },
            isCurrentSubStudy: function() {
                return this.currentStudy === this.subStudyIdentifier;
            },
            setErrorMessage: function(message) {
                var errorEl = document.querySelector("#instrumentsExportErrorMessage");
                if (!errorEl) return;
                errorEl.innerText = message;
            },
            getInstrumentList: function () {
                var self = this;
                //set sub-study elements vis
                Global.setSubstudyElementsVis(".sub-study", (data) => {
                    tnthAjax.getInstrumentsList(false, function (data) {
                        if (!data || !data.length) {
                            self.setErrorMessage(data.error);
                            self.setInstrumentsListReady();
                            return false;
                        }
                        self.setErrorMessage("");
                        let entries = data.sort();
                        self.setMainStudyInstrumentsListContent(entries);
                        self.setSubStuyInstrumentsListContent(entries);
                        self.setInstrumentsListReady();
                        setTimeout(function() {
                            self.setInstrumentInputEvent();
                        }.bind(self), 150);
                    });
                });
            },
            isSubStudyInstrument: function(instrument_code) {
                if (!instrument_code) return false;
                let re = new RegExp(EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER, "i");
                if (re.test(instrument_code)) {
                    return true;
                }
            },
            setMainStudyInstrumentsListContent: function(list) {
                if (!list) return false;
                this.mainStudyInstrumentsList = list.filter(code => {
                    return !this.isSubStudyInstrument(code);
                });
            },
            setSubStuyInstrumentsListContent: function(list) {
                if (!list) return false;
                this.subStudyInstrumentsList = list.filter(code => {
                    return this.isSubStudyInstrument(code);
                });
            },
            getDisplayInstrumentName: function(code) {
                if (!code) return "";
                return code.replace(/_/g, " ").toUpperCase();
            },
            setInstrumentInputEvent: function() {
                var self = this;
                $("#patientsInstrumentList [name='instrument']").on("click", function(event) {
                    let arrSelected = [];
                    $("input[name=instrument]").each(function() {
                        if ($(this).is(":checked")) {
                            arrSelected.push($(this).val());
                            $(this).closest("label").addClass("active");
                        } else $(this).closest("label").removeClass("active");
                    });
                    if (!arrSelected.length) {
                        self.instruments.selected = [];
                        return;
                    }
                    self.instruments.selected = arrSelected;
                });
                $("#patientsInstrumentList [name='instrument'], #patientsDownloadTypeList [name='downloadType']").on("click", function() {
                    //clear pre-existing export info display
                    self.resetExportInfoUI();
                    if (self.hasInstrumentsSelection()) {
                        $("#patientsDownloadButton").removeAttr("disabled");
                    }
                });
                //patientsDownloadTypeList downloadType
                $("#patientsDownloadTypeList [name='downloadType']").on("click", function() {
                    $("#patientsDownloadTypeList label").removeClass("active");
                    if ($(this).is(":checked")) {
                        $(this).closest("label").addClass("active");
                        return;
                    }
                });
                $("#dataDownloadModal").on("show.bs.modal", function () {
                    self.resetExportInfoUI();
                    self.setInstrumentsListReady();
                    self.instruments.selected = [];
                    self.instruments.dataType = "csv";
                    $(this).find("#patientsInstrumentList label").removeClass("active");
                    $(this).find("[name='instrument']").prop("checked", false);
                });
            },
            resetExportInfoUI: function() {
                this.$refs.exportDataLoader.clearInProgress();
            },
            setInProgress: function(inProgress) {
                if (!inProgress) {
                    this.resetExportInfoUI();
                    return;
                }
                this.$refs.exportDataLoader.setInProgress(true);
            },
            initExportEvent: function() {
                /*
                 * custom UI events associated with exporting data
                 */
                let self = this;
                 $("#dataDownloadModal").on("hide.bs.modal", function () {
                    self.setInProgress(false);
                });
                $(window).on("focus", function() {
                    self.handleSetExportHistory();
                });
            },
            setDataType: function (event) {
                this.instruments.showMessage = false;
                this.instruments.dataType = event.target.value;
            },
            resetInstrumentSelections: function() {
                $("#patientsInstrumentList [name='instrument']").prop("checked", false);
                $("#patientsInstrumentList label").removeClass("active");
                this.instruments.selected = [];
            },
            setInstrumentsListReady: function() {
                Vue.nextTick(function() {
                    document.querySelector("#patientsInstrumentList").classList.add("ready");
                });
            },
            hasInstrumentsSelection: function () {
                return (this.instruments.selected && this.instruments.selected.length) && this.instruments.dataType !== "";
            },
            getExportUrl: function() {
                if (!this.hasInstrumentsSelection()) return "";
                var queryStringInstruments = (this.instruments.selected).map(item => `instrument_id=${item}`).join("&");
                return `/api/patient/assessment?${queryStringInstruments}&format=${this.instruments.dataType}`;
            },
            getDefaultExportObj: function() {
                return {
                    study: this.currentStudy,
                    date: new Date().toLocaleString(),
                    instruments: this.instruments.selected || []
                }
            },
            handleInitExport: function(statusUrl) {
                if (!statusUrl) return;
                // whenever the user initiates an export, we cache the associated celery task URL
                this.setCacheTask({
                    ...this.getDefaultExportObj(),
                    url: statusUrl
                });
                this.currentTaskUrl = statusUrl;
            },
            handleAfterExport: function(resultUrl) {
                //export is done, save the last export to local storage
                this.setCacheExportedDataInfo(resultUrl);
            },
            getCacheExportTaskKey: function() {
                return `export_data_task_${this.getUserId()}_${this.currentStudy}`;
            },
            removeCacheTaskURL: function() {
                localStorage.removeItem(this.getCacheExportTaskKey());
            },
            setCacheTask: function(taskObj) {
                if (!taskObj) return;
                localStorage.setItem(this.getCacheExportTaskKey(), JSON.stringify(taskObj));
            },
            getCacheTask: function() {
                const task = localStorage.getItem(this.getCacheExportTaskKey());
                if (!task) return null;
                let resultJSON = null;
                try {
                    resultJSON = JSON.parse(task);
                } catch(e) {
                    console.log("Unable to parse task JSON ", e);
                    resultJSON = null;
                }
                return resultJSON;
            },
            getFinishedStatusURL: function(url) {
                if (!url) return "";
                return url.replace("/status", "");
            },
            getExportDataInfoFromTask: function(callback) {
                callback = callback || function() {};
                const task = this.getCacheTask();
                const self = this;
                if (!task) {
                    callback({data: null});
                    return;
                }
                const taskURL = task.url;
                if (!taskURL) {
                    callback({data: null});
                    return;
                }
                $.getJSON(taskURL, function(data) {
                    if (!data) {
                        callback({data: null});
                        return;
                    }
                    // check the status of the celery task and returns the data if it had been successful
                    const exportStatus = String(data["state"]).toUpperCase();
                    callback({
                                data : 
                                    exportStatus === "SUCCESS"? 
                                    {
                                        ...task,
                                        url: self.getFinishedStatusURL(taskURL)
                                    }:
                                    null
                            });
                    // callback({
                    //     data: {
                    //         ...task,
                    //         url: self.getFinishedStatusURL(taskURL)
                    //     }
                    // })
                }).fail(function() {
                    callback({data: null});
                });
            },
            getCacheExportedDataInfoKey: function() {
                //uniquely identified by each user and the study
                return `exporDataInfo_${this.getUserId()}_${this.currentStudy}`;
            },
            setCacheExportedDataInfo: function(resultUrl) {
                if (!resultUrl) return false;
                if (!this.hasInstrumentsSelection()) return;
                var o = {
                    ...this.getDefaultExportObj(),
                    url: resultUrl
                };
                localStorage.setItem(this.getCacheExportedDataInfoKey(), JSON.stringify(o));
                this.setExportHistory(o);
            },
            getCacheExportedDataInfo: function() {
                let cachedItem = localStorage.getItem(this.getCacheExportedDataInfoKey());
                if (!cachedItem) {
                    return null;
                }
                let resultJSON = null;
                try {
                    resultJSON = JSON.parse(cachedItem);
                } catch(e) {
                    console.log("Unable to parse cached data export info ", e);
                    resultJSON = null;
                }
                return resultJSON;
            },
            hasExportHistory: function() {
                return this.exportHistory || this.getCacheExportedDataInfo();
            },
            setExportHistory: function(o) {
                this.exportHistory = o;
            },
            handleSetExportHistory: function() {
                const self = this;
                this.getExportDataInfoFromTask(function(data) {
                    if (data && data.data) {
                        const task = this.getCacheTask();
                      //  console.log("current task URL ", self.getFinishedStatusURL(self.currentTaskUrl));
                      //  console.log("cached task URL ", self.getFinishedStatusURL(task.url));
                        if (task &&
                            task.url &&
                            self.getFinishedStatusURL(task.url) === self.getFinishedStatusURL(self.currentTaskUrl)) {
                            this.setInProgress(false);
                        }
                        return;
                    }
                    const cachedDataInfo = this.getCacheExportedDataInfo();
                    if (cachedDataInfo) {
                        this.setExportHistory(cachedDataInfo);
                    }
                }.bind(this));
            }
        }
    };
</script>
