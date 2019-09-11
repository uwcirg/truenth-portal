<template>
    <div>
        <div class="modal fade" id="dataDownloadModal" tabindex="-1" role="dialog">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal" :aria-label="closeLabel"><span aria-hidden="true">&times;</span></button>
                        <span v-text="title"></span>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label class="text-muted" v-text="instrumentsPromptLabel"></label>
                            <div id="patientsInstrumentListWrapper">
                                <!-- dynamically load instruments list -->
                                <div id="patientsInstrumentList" class="profile-radio-list"></div>
                                <div id="instrumentListLoad"><i class="fa fa-spinner fa-spin fa-2x loading-message"></i></div>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="text-muted" v-text="dataTypesPromptLabel"></label>
                            <div id="patientsDownloadTypeList" class="profile-radio-list">
                                <label class="radio-inline" v-for="item in dataTypes" :key="item.id">
                                    <input type="radio" name="downloadType" :id="item.id" :value="item.value" @click="setDataType" :checked="item.value == 'csv'"/>
                                    {{item.label}}
                                </label>
                            </div>
                        </div>
                        <br/>
                        <div id="instrumentsExportErrorMessage" class="error-message"></div>
                        <div class="text-center exportReport__display-container">
                            <span class="exportReport__status"></span>
                            <span class="exportReport__percentage"></span>
                            <span class="exportReport__result"></span>
                            <div class="exportReport__error"><div class="message"></div></div>
                            <div class="exportReport__retry"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-default" id="patientsDownloadButton" :disabled="!hasInstrumentsSelection()" v-text="exportLabel"></button>
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
    import tnthAjax from "../modules/TnthAjax.js";
    import ExportInstrumentsData from "../data/common/ExportInstrumentsData.js";
    export default { /*global i18next */
        props: {
            instrumentsList: {
                type: Array,
                required: false
            }
        },
        data: function() {
            return ExportInstrumentsData;
        },
        mounted: function() {
            this.getInstrumentList();
            this.initExportUIEvent();
        },
        methods: {
            getInstrumentList: function () {
                if (this.instrumentsList && this.instrumentsList.length) {
                    this.setInstrumentsListContent(this.instrumentsList);
                    this.setInstrumentInputEvent();
                    return;
                }
                var self = this;
                tnthAjax.getInstrumentsList(false, function (data) {
                    if (!data || !data.length) {
                        document.querySelector("#instrumentsExportErrorMessage").innerText = data.error;
                        document.querySelector("#patientsInstrumentList").classList.add("ready");
                        return false;
                    }
                    document.querySelector("#instrumentsExportErrorMessage").innerText = "";
                    self.setInstrumentsListContent(data.sort());
                    setTimeout(function() {
                        self.setInstrumentInputEvent();
                    }.bind(self), 150);
                });
            },
            setInstrumentsListContent: function(list) {
                let content = "";
                (list).forEach(function(code) {
                    content += `<div class="checkbox instrument-container" id="${code}_container"><label><input type="checkbox" name="instrument" value="${code}">${code.replace(/_/g, " ").toUpperCase()}</label>`;
                });
                document.querySelector("#patientsInstrumentList").innerHTML = content;
                document.querySelector("#patientsInstrumentList").classList.add("ready");
            },
            setInstrumentInputEvent: function() {
                var self = this;
                $("#patientsInstrumentList [name='instrument']").on("click", function(event) {
                    if (event.target.value && $(event.target).is(":checked")) {
                        self.instruments.selected = self.instruments.selected + (self.instruments.selected !== "" ? "&" : "") + "instrument_id=" + event.target.value;
                        return;
                    }
                    if ($("input[name=instrument]:checked").length === 0) {
                        self.instruments.selected = "";
                    }
                });
                $("#dataDownloadModal").on("show.bs.modal", function () {
                    self.instruments.selected = "";
                    self.instruments.dataType = "csv";
                    $("#patientsInstrumentList").addClass("ready");
                    $(this).find("[name='instrument']").prop("checked", false);
                });
                $("#dataDownloadModal").on("hide.bs.modal", function() {
                    //reset export vis
                    self.clearExportReportUI();
                });
            },
            setDataType: function (event) {
                this.instruments.showMessage = false;
                this.instruments.dataType = event.target.value;
            },
            getExportUrl: function() {
                return `/api/patient/assessment?${this.instruments.selected}&format=${this.instruments.dataType}`;
            },
            clearExportReportTimeoutID: function() {
                if (!this.arrExportReportTimeoutID.length) {
                    return false;
                }
                let self = this;
                for (var index=0; index < self.arrExportReportTimeoutID.length; index++) {
                    clearTimeout(self.arrExportReportTimeoutID[index]);
                }
            },
            //TODO refactor these methods so they can be re-used
            clearExportReportUI: function() {
                $(".exportReport__display-container").removeClass("active");
                $(".exportReport__error .message").html("");
                $(".exportReport__retry").addClass("tnth-hide");
            },
            onBeforeExportReportData: function() {
                $("#patientsDownloadButton").attr("disabled", true);
                $(".exportReport__display-container").addClass("active");
                $(".exportReport__status").addClass("active");
            },
            onAfterExportReportData: function(options) {
                options = options || {};
                $("#patientsDownloadButton").attr("disabled", false);
                $(".exportReport__status").removeClass("active");
                if (options.error) {
                    this.updateProgressDisplay("", "");
                    $(".exportReport__error .message").html("Request to export report data failed.");
                    $(".exportReport__retry").removeClass("tnth-hide");
                    return;
                }
                $(".exportReport__error .message").html("");
                $(".exportReport__retry").addClass("tnth-hide");
            },
            initExportUIEvent: function() {
                const DELAY_INTERVAL = 50;
                let self = this;
                $("#patientsDownloadButton").on("click", function(e) {
                    e.stopPropagation();
                    let dataType = $(this).attr("data-type");
                    let reportUrl = self.getExportUrl();
                    self.updateProgressDisplay("", "");
                    setTimeout(function() {
                        self.onBeforeExportReportData();
                    }, DELAY_INTERVAL);
                    $.ajax({
                        type: 'GET',
                        url: reportUrl,
                        success: function(data, status, request) {
                            let statusUrl= request.getResponseHeader("Location");
                            self.updateExportProgress(statusUrl, function(data) {
                                self.onAfterExportReportData(data);
                            });
                        },
                        error: function(xhr) {
                            self.onAfterExportReportData({error: true});
                        }
                    });
                });
            },
            updateProgressDisplay: function(status, percentage, showLoader) {
                $(".exportReport__percentage").text(percentage);
                $(".exportReport__status").text(status);
                if (showLoader) {
                    $(".exportReport__loader").removeClass("tnth-hide");
                } else {
                    $(".exportReport__loader").addClass("tnth-hide")
                }
            },
            updateExportProgress: function(statusUrl, callback) {
                callback = callback || function() {};
                if (!statusUrl) {
                    callback({error: true});
                    return;
                }
                let self = this;
                // send GET request to status URL
                let rqId = $.getJSON(statusUrl, function(data) {
                    if (!data) {
                        callback({error: true});
                        return;
                    }
                    let percent = "0%", exportStatus = data["state"].toUpperCase();
                    if (data["current"] && data["total"] && parseInt(data["total"]) > 0) {
                        percent = parseInt(data['current'] * 100 / data['total']) + "%";
                    }
                    //update status and percentage displays
                    self.updateProgressDisplay(exportStatus, percent, true);
                    let arrIncompleteStatus = ["PENDING", "PROGRESS", "STARTED"];
                    if (arrIncompleteStatus.indexOf(exportStatus) === -1) {
                        if (exportStatus === "SUCCESS") {
                            setTimeout(function() {
                                let resultUrl = statusUrl.replace("/status", "");
                                window.location.assign(resultUrl);
                            }.bind(self), 50); //wait a bit before retrieving results
                        }
                        self.updateProgressDisplay(data["state"], "");
                        setTimeout(function() {
                            callback();
                        }, 300);
                    }
                    else {
                        // rerun in 2 seconds
                        self.exportReportTimeoutID = setTimeout(function() {
                            self.updateExportProgress(statusUrl, callback);
                        }.bind(self), 2000); //each update invocation should be assigned a unique timeoutid
                        (self.arrExportReportTimeoutID).push(self.exportReportTimeoutID);
                    }
                }).fail(function() {
                    callback({error: true});
                });
            },
            hasInstrumentsSelection: function () {
                return this.instruments.selected !== "" && this.instruments.dataType !== "";
            }
        }
    };
</script>
