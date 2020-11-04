<template>
	<div id="assessmentReportContentContainer">
		<div class="error-message" v-show="errorMessage !== ''">
			<br/>{{errorMessage}}<br/>
		</div>
		<div class="container">
			<div class="row">
				<div class="col-md-12">
					<div id="userSessionReportDetail" cellpadding="2">
						<table class="tnth-admin-table table table-condensed table-striped table-bordered small-text" id="userSessionReportDetailTable" v-if="data.length > 0">
							<caption>
								<hr/>
								<span class="profile-item-title">{{caption.title}}</span>
								<br/>
								<span class="text-muted smaller-text">{{caption.lastUpdated}}</span>
								<span class='gmt'>{{caption.timezone}}</span>
								<hr/>
							</caption>
							<THEAD>
								<TH v-for="(item,index) in tableHeaders" :key="index" v-text="item"></TH>
							</THEAD>
							<TBODY>
								<TR v-for="(item,index) in data" :key="index">
									<TD v-html="item.q"></TD>
									<TD v-html="item.a"></TD>
								</TR>
							</TBODY>
						</table>
						<br/>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
<script>
    import AssessmentReportData from "../data/common/AssessmentReportData.js";
    import tnthDates from "../modules/TnthDate.js";
	export default {
    /* global i18next */
    data: function() {
        return AssessmentReportData;
    },
    mounted: function() {
        var self = this;
        $(function() {
            self.getData();
            if (!("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch)) {
                /*global DocumentTouch*/
                $("#userSessionReportDetailHeader [data-toggle='tooltip']").tooltip();
            }
        });
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
                    self.errorMessage = self.serverError;
                    return;
                }
                if (!data.entry || !data.entry.length) {
                    self.errorMessage = self.noDataError;
                    return;
                }
                var entries = data.entry;
                var entry;
                entry = $.grep(entries, function(item) {
                    return String(item.authored) === String(sessionAuthoredDate);
                });
                entry = entry[0] || entries[0];
                self.caption.title = i18next.t(entries[0].questionnaire.display);
                self.caption.lastUpdated = tnthDates.setUTCDateToLocaleDateString(sessionAuthoredDate);
                self.caption.timezone = i18next.t("GMT, Y-M-D");
                (entry.group.question).forEach(function(entry) {
                    var q = (entry.text ? entry.text.replace(/^[\d\w]{1,3}\./, "") : ""),
                        a = "";
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
                    q = !self.hasValue(q) ? "--" : q;
                    a = !self.hasValue(a) ? "--" : a;
                    self.data.push({
                        q: q,
                        a: a
                    });
                });
            }).fail(function() {
                self.errorMessage = self.loadError;
            });
        }
    }
};
</script>


