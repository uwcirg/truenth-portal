(function() {
    var i18next = window.portalModules.i18next, tnthDates = window.portalModules.tnthDates;
    var AssessmentReportObj = new Vue({ /*global Vue $*/
        el: "#userSessionReportMainContainer",
        data: {
            userId: $("#_report_user_id").val(),
            reportDate: $("#_report_authored_date").val(),
            instrumentId: $("#_report_instrument_id").val(),
            errorMessage: "",
            data: [],
            caption: {}
        },
        methods: {
            hasValue: function(s) {
                return String(s) !== "" && String(s) !== "undefined" && s !== null;
            },
            getData: function() {
                var self = this;
                $.ajax({
                    type: "GET",
                    url: "/api/patient/" + this.userId + "/assessment/" + this.instrumentId
                }).done(function(data) {
                    var sessionAuthoredDate = $("#_report_authored_date").val();
                    self.errorMessage = "";
                    if (data.error) {
                        self.errorMessage = i18next.t("Server Error occurred retrieving report data");
                    } else {
                        if (data.entry && data.entry.length > 0) {
                            var entries = data.entry;
                            var entry;

                            entries.forEach(function(item) {
                                if (!entry && (String(item.authored) === String(sessionAuthoredDate))) {
                                    entry = item;
                                }
                            });

                            entry = entry || entries[0];
                            self.caption.title = i18next.t(entries[0].questionnaire.display);
                            self.caption.lastUpdated = tnthDates.formatDateString(sessionAuthoredDate, "iso");
                            self.caption.timezone = i18next.t("GMT, Y-M-D");

                            (entry.group.question).forEach(function(entry) {
                                var q = (entry.text ? entry.text.replace(/^[\d\w]{1,3}\./, "") : ""), a = "";
                                if (entry.answer) {
                                    (entry.answer).forEach(function(item) {
                                        if (self.hasValue(item.valueString)) {
                                            a += (a ? "<br/>" : "") + item.valueString;
                                        }
                                    });
                                }

                                /*
                                 * using valueCoding.code for answer and linkId for question if BOTH question and answer are empty strings
                                 */

                                if (!q && !a) {
                                    q = entry.linkId;
                                    (entry.answer).forEach(function(item) {
                                        if (item.valueCoding && item.valueCoding.code) {
                                            a += (a ? "<br/>" : "") + item.valueCoding.code;
                                        }
                                    });
                                }

                                if (!self.hasValue(q)) {
                                    q = "--";
                                }
                                if (!self.hasValue(a)) {
                                    a = "--";
                                }
                                self.data.push({ q: q, a: a});
                            });
                        }
                    }

                }).fail(function() {
                    self.errorMessage = i18next.t("Unable to load report data");
                });
            }
        }
    });
    $(function() {
        AssessmentReportObj.getData();
        if (!("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch)) {
            $('#userSessionReportDetailHeader [data-toggle="tooltip"]').tooltip();
        }
    });
})();
