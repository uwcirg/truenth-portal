(function() {
    var AssessmentReportObj = new Vue({ /*global Vue i18next $*/
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
                            entry = $.grep(entries, function(item) {
                                return String(item.authored) === String(sessionAuthoredDate);
                            });
                            entry = entry[0] || entries[0];
                            self.caption.title = i18next.t(entries[0].questionnaire.display);
                            var lastUpdatedDateObj = new Date(sessionAuthoredDate);
                            self.caption.lastUpdated = new Date(lastUpdatedDateObj.toUTCString().slice(0, -4));
                            self.caption.lastUpdated = self.caption.lastUpdated.toLocaleDateString("en-GB", { //use native date function
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit"
                            });
                            self.caption.timezone = i18next.t("GMT, Y-M-D");
                            (entry.group.question).forEach(function(entry) {
                                var q = (entry.text ? entry.text.replace(/^[\d\w]{1,3}\./, "") : ""), a = "";
                                entry.answer = entry.answer || [];
                                var arrValueStrings = $.grep(entry.answer, function(item) {
                                    return self.hasValue(item.valueString);
                                });
                                arrValueStrings = arrValueStrings.map(function(item) {
                                    return item.valueString;
                                });
                                a = arrValueStrings.join("<br/>");
                                /*
                                 * using valueCoding.code for answer and linkId for question if BOTH question and answer are empty strings
                                 */
                                if (!q && !a) {
                                    q = entry.linkId;
                                    var arrValueCoding = $.grep(entry.answer, function(item) {
                                        return item.valueCoding && item.valueCoding.code;
                                    });
                                    arrValueCoding = arrValueCoding.map(function(item) {
                                        return item.valueCoding.code;
                                    });
                                    a = arrValueCoding.join("<br/>");
                                }
                                q = !self.hasValue(q)? "--": q;
                                a = !self.hasValue(a)? "--": a;
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
        if (!("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch)) { /*global DocumentTouch*/
            $("#userSessionReportDetailHeader [data-toggle='tooltip']").tooltip();
        }
    });
})();
