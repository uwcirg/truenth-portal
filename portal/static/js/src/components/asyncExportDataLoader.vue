<!--
    helper component for making ajax call to initiate the ajax call for exporting data and display progress status on UI
-->
<template>
    <div class="text-center export__display-container">
        <div class="text-info text-center"><h4 v-text="requestSubmittedDisplay"></h4></div>
        <span class="export__status"></span>
        <span class="export__percentage"></span>
        <span class="export__result"></span>
        <div class="export__error"><div class="message"></div></div>
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
            }
        },
        data: function() {
            return {
                exportDataTimeoutID: 0,
                statusDisplayTimeoutID: 0,
                arrExportDataTimeoutID: [],
                arrIncompleteStatus: ["PENDING", "PROGRESS", "STARTED"],
                requestSubmittedDisplay: ExportInstrumentsData["requestSubmittedDisplay"],
                failedRequestDisplay: ExportInstrumentsData["failedRequestDisplay"]
            }
        },
        mounted: function() {
            this.initExportUIEvent();
        },
        methods: {
            getExportUrl: function() {
                return this.exportUrl;
            },
            isSuccessStatus: function(status) {
                return String(status).toUpperCase() === "SUCCESS";
            },
            clearExportDataUI: function() {
                $(".export__display-container").removeClass("active");
                $(".export__error .message").html("");
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
            onBeforeExportData: function() {
                this.clearExportDataTimeoutID();
                this.clearExportDataUI();
                $("#" + this.initElementId).attr("disabled", true);
                $(".export__display-container").addClass("active");
                $(".export__status").addClass("active");
            },
            onAfterExportData: function(options) {
                options = options || {};
                $("#" + this.initElementId).attr("disabled", false);
                $(".export__status").removeClass("active");
                //clear display when download has successfully completed
                this.statusDisplayTimeoutID = setTimeout(function() {
                    this.clearExportDataUI();
                }.bind(this), 5000);
                if (options.error) {
                    this.updateProgressDisplay("", "");
                    $(".export__error .message").html(this.failedRequestDisplay + (options.message? "<br/>"+options.message: ""));
                    return;
                }
                $(".export__error .message").html("");
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
                            self.onAfterExportData({error: true});
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
                let self = this;
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
                    }
                    //update status and percentage displays
                    self.updateProgressDisplay(exportStatus, percent, true);
                    if (self.arrIncompleteStatus.indexOf(exportStatus) === -1) {
                        if (self.isSuccessStatus(exportStatus)) {
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
                        self.exportDataTimeoutID = setTimeout(function() {
                            self.updateExportProgress(statusUrl, callback);
                        }.bind(self), 5000); //each update invocation should be assigned a unique timeoutid
                        (self.arrExportDataTimeoutID).push(self.exportDataTimeoutID);
                    }
                }).fail(function() {
                    callback({error: true});
                });
            }
        }
    }
</script>
