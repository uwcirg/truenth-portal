<!--
    helper component for making ajax call to initiate the ajax call for exporting data and display progress status on UI
-->
<template>
    <div class="text-center export__display-container">
        <div class="text-info text-center export__info"><h4 v-text="requestSubmittedDisplay"></h4></div>
        <span class="export__status"></span>
        <span class="export__percentage"></span>
        <span class="export__result"></span>
        <div class="export__error text-left"><div class="message"></div></div>
    </div>
</template>
<script>
    import ExportInstrumentsData from "../data/common/ExportInstrumentsData.js";
    export default {
        props: {
            //element that will initiate export process e.g. via click event
            initElementId: {
                 type: String,
                 required: true
            },
            //endpoint for exporting data
            exportUrl: {
                type: String,
                required: true
            },
            //unique identifier exports, e.g. substudy vs main study
            exportIdentifier: {
                type: String
            }
        },
        watch: {
            exportIdentifier: function (newValue, oldValue) {
                //if export identifier changes, stop all running jobs
                this.clearExportDataTimeoutID();
            }
        },
        data: function() {
            return {
                exportDataTimeoutID: 0,
                exportTimeElapsed: 0,
                statusDisplayTimeoutID: 0,
                arrExportDataTimeoutID: [],
                maximumPendingTime: 60000, //allow 60 seconds of PENDING status
                arrIncompleteStatus: ["PENDING", "PROGRESS", "STARTED"],
                requestSubmittedDisplay: ExportInstrumentsData["requestSubmittedDisplay"],
                failedRequestDisplay: ExportInstrumentsData["failedRequestDisplay"]
            }
        },
        mounted: function() {
            this.initExportUIEvent();
            //initiate any parent custom export event passed to the component
            this.$emit("initExportCustomEvent");
        },
        methods: {
            getExportUrl: function() {
                return this.exportUrl;
            },
            isSuccessStatus: function(status) {
                return String(status).toUpperCase() === "SUCCESS";
            },
            isInProgress: function() {
                return $("#"+this.initElementId).attr("data-export-in-progress");
            },
            setInProgress: function(isInProgress) {
                if (isInProgress) {
                    $("#"+this.initElementId).attr("data-export-in-progress", true);
                    return;
                }
                $("#"+this.initElementId).removeAttr("data-export-in-progress");
            },
            clearExportDataUI: function() {
                $(".export__display-container").removeClass("active");
                $(".export__error .message").html("");
                $(".export__info").html("");
                clearTimeout(this.statusDisplayTimeoutID);
            },
            clearExportDataTimeoutID: function() {
                if (!this.arrExportDataTimeoutID.length) {
                    return false;
                }
                let self = this;
                for (var index=0; index < self.arrExportDataTimeoutID.length; index++) {
                    clearTimeout(self.arrExportDataTimeoutID[index]);
                }
            },
            clearTimeElapsed: function() {
                this.exportTimeElapsed = 0;
            },
            onBeforeExportData: function() {
                this.updateExportProgress("", "");
                this.clearExportDataTimeoutID();
                this.clearTimeElapsed();
                this.clearExportDataUI();
                this.setInProgress(true);
                $("#" + this.initElementId).attr("disabled", true);
                $(".export__display-container").addClass("active");
                $(".export__status").addClass("active");
            },
            setMessage: function(message) {
                message = message || "";
                $(".export__error .message").html(message);
            },
            onAfterExportData: function(options) {
                options = options || {};
                let delay = options.delay||5000;
                $("#" + this.initElementId).attr("disabled", false);
                $(".export__status").removeClass("active");
                this.setInProgress();
                if (options.error) {
                    this.updateProgressDisplay("", "");
                    this.setMessage(this.failedRequestDisplay + (options.message? "<br/>"+options.message: ""));
                    return;
                }
                this.setMessage("");
            },
            initExportUIEvent: function() {
                let self = this;
                $("#" + this.initElementId).on("click", function(e) {
                    e.stopPropagation();
                    let exportDataUrl = self.getExportUrl();
                    self.updateProgressDisplay("", "");
                    /*
                     * clear UI and any impending requests and start anew
                     */
                    self.onBeforeExportData();
                    $.ajax({
                        type: "GET",
                        url: exportDataUrl,
                        success: function(data, status, request) {
                            let statusUrl= request.getResponseHeader("Location");
                            self.updateExportProgress(statusUrl, function(data) {
                                self.onAfterExportData(data);
                            });
                        },
                        error: function(xhr) {
                            self.onAfterExportData({error: true, message: xhr.responseText});
                        }
                    });
                });
            },
            updateProgressDisplay: function(status, percentage, showLoader) {
                if (this.isSuccessStatus(status)) {
                    status = `<span class="text-success">${status}</span>`;
                }
                $(".export__percentage").text(percentage);
                $(".export__status").html(status);
                if (showLoader) {
                    $(".export__loader").removeClass("tnth-hide");
                } else {
                    $(".export__loader").addClass("tnth-hide")
                }
            },
            updateExportProgress: function(statusUrl, callback) {
                callback = callback || function() {};
                if (!statusUrl) {
                    callback({error: true});
                    return;
                }
                if (!this.isInProgress()) {
                    this.updateProgressDisplay("", "");
                    this.clearExportDataUI();
                    return false;
                }
                let self = this;
                let waitTime = 3000;
                // send GET request to status URL
                let rqId = $.getJSON(statusUrl, function(data) {
                    if (!data) {
                        callback({error: true});
                        return;
                    }
                    let percent = "0%", exportStatus = data["state"].toUpperCase();
                    /*
                     * for some reason the export status is not returned, has the celery job timed out?
                     */
                    if (!exportStatus) {
                        //return a specific message here so we know that the status is not being returned
                        callback({error: true, message: "no export status available."});
                        return;
                    }
                    if (data["current"] && data["total"] && parseInt(data["total"]) > 0) {
                        percent = parseInt(data['current'] * 100 / data['total']) + "%";
                    } else {
                        percent = " -- %";
                        //allow maximum allowed elapsed time of pending status and no progress percentage returned, 
                        //if still no progress returned, then return error and display message
                        if (exportStatus === "PENDING" && self.exportTimeElapsed > self.maximumPendingTime) {
                            callback({error: true, message: "Processing job not responding. Please try again.", delay: 10000});
                            return;
                        }
                    }
                    //update status and percentage displays
                    self.updateProgressDisplay(exportStatus, percent, true);
                    if (self.arrIncompleteStatus.indexOf(exportStatus) === -1) {
                        if (self.isSuccessStatus(exportStatus)) {
                            let resultUrl = statusUrl.replace("/status", "");
                            self.$emit("doneExport", resultUrl);
                            setTimeout(function() {
                                window.location.assign(resultUrl);
                            }, 50); //wait a bit before retrieving results
                        }
                        self.updateProgressDisplay(data["state"], "");
                        setTimeout(function() {
                            callback();
                        }, 300);
                    }
                    else {
                        // rerun in 3 seconds
                        self.exportTimeElapsed += waitTime;
                        self.exportDataTimeoutID = setTimeout(function() {
                            self.updateExportProgress(statusUrl, callback);
                        }.bind(self), waitTime); //each update invocation should be assigned a unique timeoutid
                        (self.arrExportDataTimeoutID).push(self.exportDataTimeoutID);
                    }
                }).fail(function() {
                    callback({error: true});
                });
            }
        }
    }
</script>
