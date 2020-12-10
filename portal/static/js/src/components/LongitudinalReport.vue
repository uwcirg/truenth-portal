<template>
	<div id="longitudinalReportContainer" class="report">
        <div class="loader" v-show="loading"><i class="fa fa-spinner fa-spin fa-2x"></i></div>
		<div class="error-message" v-show="hasValue(errorMessage)" v-html="errorMessage"></div>
        <div class="content" :class="{triggers:hasTriggers()}" v-show="!loading">
            <div v-show="hasTriggers()" class="text-muted text-right report-legend" :class="{active: hasTriggers()}">
                <span class="title" v-text="triggerLegendTitle"></span>
                <span class="hard-trigger-legend" v-text="hardTriggerLegend"></span>
                <span class="soft-trigger-legend" v-text="softTriggerLegend"></span>
            </div>
            <span class="nav-arrow start" @click="setGoBackward()" v-show="!hasValue(errorMessage)">&lt;</span>
            <span class="nav-arrow end" @click="setGoForward()" v-show="!hasValue(errorMessage)">&gt;</span>
            <table class="report-table" v-show="!hasValue(errorMessage)">
                <THEAD>
                    <TH class="title" v-text="questionTitleHeader"></TH>
                    <TH class="cell date" :data-column-index="index+1" v-for="(item, index) in questionnaireDates" :key="'head_'+index" v-html="item"></TH>
                </THEAD>
                <TBODY>
                    <TR v-for="(item, qindex) in questions" :key="'question_'+ qindex">
                        <TD class="item question domain" v-if="item.displayDomain">
                            <span class= "domainText">{{item.code[0].display}}</span>
                            {{item.text}}
                        </TD>
                        <TD class="item question" v-html="item.text" v-else></TD>
                        <TD class="cell item" v-for="(d, index) in item.data" :key="'answer_'+qindex+'_'+index" :data-column-index="index+1">
                            <span class="answer" v-html="d.a" v-bind:class="d.cssClass"></span>
                        </TD>
                    </TR>
                </TBODY>
            </table>
        </div>
	</div>
</template>
<script>
    import AssessmentReportData from "../data/common/AssessmentReportData.js";
    import tnthDates from "../modules/TnthDate.js";
    import SYSTEM_IDENTIFIER_ENUM from "../modules/SYSTEM_IDENTIFIER_ENUM";
    import {EMPRO_TRIGGER_PROCCESSED_STATES} from "../data/common/consts.js";
	export default {
    data () {
        return {
            ...AssessmentReportData,
            userId: 0,
            data: [{
                date: "",
                data: []
            }],
            questionnaireData:[],
            assessmentData:[],
            triggerData: {
                data: [],
                hardTriggers: [],
                softTriggers: []
            },
            questionnaireDates: [],
            questions: [{
                code: "",
                linkId: "",
                text: ""
            }],
            loading: true,
            maxToShow: 1,
            navStartIndex: 1,
            navEndIndex: 1,
            domains: [],
            instrumentId: "",
            errorMessage: ""
        }
    },
    mounted () {
        this.setUserId();
        this.setInstrumentId();
        this.setMaxToShow();
        this.initEvents();
        this.getData();
    },
    methods: {
        setUserId () {
            this.userId = location.pathname.split("/")[2];
        },
        setInstrumentId () {
            this.instrumentId = location.pathname.split("/")[4];
        },
        setInitVis() {
            this.setMaxToShow();
            this.setNavIndexes();
            this.setNavCellVis();
            this.setPrintStyle();
            setTimeout(function() {
                this.loading = false;
            }.bind(this), 150);
        },
        setMaxToShow() {
            let bodyWidth = $("body").width();
            /*
             * display column(s) responsively based on viewport width
             */
            if (bodyWidth >= 1200) {
                this.maxToShow = 4;
            } else if (bodyWidth >= 992) {
                this.maxToShow = 3;
            } else if (bodyWidth >= 699) {
                this.maxToShow = 2;
            } else {
                this.maxToShow = 1;
            }
            return;
        },
        setNavIndexes() {
            /*
             * set initial indexes for start and end navigation buttons
             */
            this.navEndIndex = this.maxToShow >= this.questionnaireDates.length ? this.questionnaireDates.length: this.maxToShow;
            this.navStartIndex = 1;
        },
        setGoForward() {
            /*
             * set navigation forward 1 column
             */
            if (this.navEndIndex < this.questionnaireDates.length) {
                this.navEndIndex = this.navEndIndex + 1;
            }
            this.navStartIndex = this.navEndIndex - this.maxToShow + 1;
            this.setNavCellVis();
        },
        setGoBackward() {
             /*
             * set navigation back 1 column
             */
            this.navStartIndex = this.navStartIndex - 1 < 1 ? 1: (this.navStartIndex - 1);
            this.navEndIndex = this.navStartIndex + this.maxToShow - 1;
            this.setNavCellVis();
        },
        setNavCellVis() {
            /*
             * set navigation vis
             */
            if (this.navEndIndex >= this.questionnaireDates.length) {
                $(".report .nav-arrow.end").addClass("disabled");
            } else {
                $(".report .nav-arrow.end").removeClass("disabled");
            }
             if (this.navStartIndex <= 1) {
                $(".report .nav-arrow.start").addClass("disabled");
            } else {
                $(".report .nav-arrow.start").removeClass("disabled");
            }
            /*
             * set columns vis
             */
            $(".report-table .cell").removeClass("active").addClass("inactive");
            for (let i = this.navStartIndex; i <= this.navEndIndex; i++) {
                $(".report-table .cell[data-column-index="+i+"]").removeClass("inactive").addClass("active");
            }
        },
        setDisplayDate(date) {
            if (!date) return "";
            return tnthDates.setUTCDateToLocaleDateString(date,
                    { //date format parameters
                        day: "numeric",
                        month: "short",
                        year: "numeric"
                    });
        },
        setDomains() {
            this.domains = this.questionnaireData.item.filter(item => {
                    return item.code && item.code.length;
            }).map(item => {
                return item.code[0].code;
            });
            //de-duplicate
            this.domains = this.domains.filter((d, index) => {
                return this.domains.indexOf(d) === index;
            });
        },
        setQuestions() {
            if (!this.questionnaireData) {
                return;
            }
            this.questions = this.questionnaireData.item;
        },
        setQuestionnaireDates() {
            /*
             * available response authored dates
             */
            this.questionnaireDates = this.assessmentData.map(item => {
                return this.setDisplayDate(item.authored);
            });
        },
        getQuestionOptions(linkId) {
            if (!linkId) return [];
            let question = this.questions.filter(item => {
                return item.linkId === linkId;
            });
            return question.length ? question[0].option : [];
        },
        setTriggerData() {
            let self = this;
            this.triggerData.data.forEach(item => {
                if (!item.triggers.domain) {
                    return true;
                }
                for (let domain in item.triggers.domain) {
                    if (!Object.keys(item.triggers.domain[domain]).length) {
                        continue;
                    }
                    for (let q in item.triggers.domain[domain]) {
                        if (!item.triggers.source || !item.triggers.source.authored) {
                            continue;
                        }
                        /*
                        * get questions that trigger hard trigger
                        */
                        if (item.triggers.domain[domain][q] === "hard") {
                            self.triggerData.hardTriggers.push({
                                "authored": item.triggers.source.authored,
                                "questionLinkId": q
                            });
                        }
                        /*
                        * get questions that trigger soft trigger
                        */
                        if (item.triggers.domain[domain][q] === "soft") {
                            self.triggerData.softTriggers.push({
                                "authored": item.triggers.source.authored,
                                "questionLinkId": q
                            });
                        }
                    }
                }
            });
        },
        hasTriggers() {
            return this.triggerData.hardTriggers.length || this.triggerData.softTriggers.length;
        }, 
        setDisplayData() {
            /*
             * prepping data for display
             */
            this.assessmentData.forEach((item, index) => {
                let authoredDate = item.authored;
                this.data[index] = {
                    "date": this.setDisplayDate(item.authored),
                    "data": []};
                (item.group.question).forEach(entry => {
                    var q = (entry.text ? entry.text.replace(/^[\d\w]{1,3}\./, "") : ""),
                        a = "";
                    entry.answer = entry.answer || [];
                    var arrValueStrings = $.grep(entry.answer, (item) => {
                        return this.hasValue(item.valueString);
                    });
                    arrValueStrings = arrValueStrings.map(function(item) {
                        return item.valueString;
                    });
                    a = arrValueStrings.join("<br/>");

                    var arrValueCoding = $.grep(entry.answer, function(item) {
                        return item.valueCoding && item.valueCoding.code;
                    });
                    arrValueCoding = arrValueCoding.map(function(item) {
                        return item.valueCoding.code;
                    });
        
                    let hardTriggers = $.grep(this.triggerData.hardTriggers, subitem => {
                        let timeStampComparison = new Date(subitem.authored).toLocaleString() === new Date(authoredDate).toLocaleString();
                        let linkIdComparison = subitem.questionLinkId === entry.linkId;
                        return timeStampComparison && linkIdComparison
                    });

                    let softTriggers = $.grep(this.triggerData.softTriggers, subitem => {
                        let timeStampComparison = new Date(subitem.authored).toLocaleString() === new Date(authoredDate).toLocaleString();
                        let linkIdComparison = subitem.questionLinkId === entry.linkId;
                        return timeStampComparison && linkIdComparison;
                    });
        
                    /*
                    * using valueCoding.code for answer and linkId for question if BOTH question and answer are empty strings
                    */
                    if (!q && !a) {
                        q = entry.linkId;
                        a = arrValueCoding.join("<br/>");
                    }
                    q = !this.hasValue(q) ? "--" : q;
                    a = !this.hasValue(a) ? "--" : a;
                    let answerValue = arrValueCoding.length? parseInt(arrValueCoding[0].split(".")[2]) : 0;
                    let optionsLength = this.getQuestionOptions(entry.linkId);
                    let answerObj = {
                        q: q,
                        a: a + (hardTriggers.length?" **": (softTriggers.length?" *": "")),
                        linkId: entry.linkId,
                        value: answerValue,
                        cssClass: 
                        //last
                        answerValue >= optionsLength.length ? "darkest" : 
                        //penultimate
                        (answerValue >= optionsLength.length - 1 ? "darker": 
                        (answerValue <= 1 ? "no-value": ""))
                    };
                    this.data[index].data.push(answerObj);
                    let currentDomain = "";
                    /*
                     * get response for each question
                     */
                    this.questions.forEach(questionItem => {
                        if (questionItem.code &&
                            questionItem.code.length && 
                            currentDomain !== questionItem.code[0].code
                            ) {
                            questionItem.displayDomain = true;
                            currentDomain = questionItem.code[0].code;
                        }
                        if (questionItem.linkId === entry.linkId) {
                            if (!questionItem.data) questionItem.data = [];
                            questionItem.data.push(answerObj);
                            return false;
                        }
                    });
                });
            });
        },
        initEvents() {
            if (!this.isTouchDevice()) {
                /*global DocumentTouch*/
                $("#longitudinalReportContainer [data-toggle='tooltip']").tooltip();
            }
            $(window).on("resize", () => {
                window.requestAnimationFrame(() => {
                    this.setInitVis();
                });
            });
        },
        getData () {
            $.when(
                $.ajax(`/api/questionnaire/${this.instrumentId}?system=${SYSTEM_IDENTIFIER_ENUM.TRUENTH_QUESTIONNAIRE_CODE_SYSTEM}`),
                $.ajax(`/api/patient/${this.userId}/assessment/${this.instrumentId}`),
                $.ajax(`/api/user/${this.userId}/trigger_history`)
            ).done((questionnaireData, assessmentData, triggerData) => {
                this.errorMessage = "";
               
                if ((!questionnaireData || !questionnaireData[0]) ||
                    (!assessmentData || !assessmentData[0])) {
                    this.errorMessage = this.serverError;
                    this.loading = false;
                    return;
                }
                if (!assessmentData[0].entry || !assessmentData[0].entry.length) {
                    this.errorMessage = this.noDataError;
                    return;
                }
                this.questionnaireData = questionnaireData[0];
                this.assessmentData = (assessmentData[0].entry).sort(function(a, b) {
                                        return new Date(b.authored) - new Date(a.authored);
                                    });
                if (triggerData && triggerData[0]) {
                    this.triggerData.data = triggerData[0].filter(item => {
                        return EMPRO_TRIGGER_PROCCESSED_STATES.indexOf(item.state) !== -1 && item.triggers;
                    });
                    this.setTriggerData();
                }
                this.setDomains();
                this.setQuestions();
                this.setQuestionnaireDates();
                this.setDisplayData();
                Vue.nextTick(() => {
                        setTimeout(function() {
                            this.setInitVis();
                        }.bind(this), 150);
                    }
                );
            }).fail(e => {
                this.errorMessage = this.loadError;
                this.loading = false;
            });
        },
        setPrintStyle() {
            /*
             * print styles, TODO: add more specifics when specs are available
             */
            var styleNode = document.createElement("style");
            styleNode.type = "text/css";
            let styles = `
                @media print {
                    section.header {
                        margin-top: 0;
                    }
                    .header__div--navigation {
                        display: none;
                    }
                    #homeFooter {
                        display: none !important;
                    }
                    #tnthNavWrapper {
                        display: none;
                        visibility: hidden !important;
                    }
                    #mainNav {
                        height: 0;
                    }
                    #tnthNavMain {
                        display: none !important;
                    }
                    .nav-arrow {
                        display: none !important;
                    }
                }
            `;
            if (styleNode.styleSheet) styleNode.styleSheet.cssText = styles;
            else styleNode.appendChild(document.createTextNode(styles));
            document.getElementsByTagName("head")[0].appendChild(styleNode);
        },
        isTouchDevice() {
            return "ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch;
        },
        hasValue (s) {
            return String(s) !== "" && String(s) !== "undefined" && s !== null;
        }
    }
};
</script>
