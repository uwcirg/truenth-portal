(function() {
    var psaApp = new Vue({
            el: "#mainPsaApp",
            data: {
                userId: "",
                clinicalCode: "666",
                clinicalDisplay: "psa",
                clinicalSystem: "http://us.truenth.org/clinical-codes",
                loading: false,
                addErrorMessage: "",
                noResultMessage: i18next.t("No PSA Result To Display"),
                newItem: {
                    id: "",
                    result: "",
                    date:"",
                    edit: false
                },
                headers: [
                    i18next.t("PSA (ng/ml)"),
                    i18next.t("Date")
                ],
                items: [],
                editTitle: i18next.t("Edit PSA Result"),
                addTitle: i18next.t("Add PSA Result")
            },
            methods: {
                init: function() {
                    var self = this;
                    self.getData();
                    setTimeout(function() {
                        $("#psaDate").datepicker({"format": "d M yyyy", "forceParse": false, "endDate": new Date(), "maxViewMode": 2, "autoclose": true
                        }).on("hide", function() {
                            $("#psaDate").trigger("blur");
                        });
                        $('#addPSAModal').on('shown.bs.modal', function(e) {
                            $("#psaResult").focus();
                        }).on('hidden.bs.modal', function(e) {
                            self.clearNew();
                        });
                        $("#psaDate").on("blur", function(e) {
                            if ($(this).val()) {
                                var isValid = tnthDates.isValidDefaultDateFormat($(this).val());
                                if (!isValid) {
                                    self.addErrorMessage = i18next.t("Date must in the valid format.");
                                    return false;
                                } else {
                                    self.newItem.date = $(this).val();
                                    self.addErrorMessage = "";
                                }
                            }
                        });
                    }, 300);
                },
                onEdit: function(item) {
                    var self = this;
                    if (item) {
                        for (var prop in self.newItem) {
                            self.newItem[prop] = item[prop];
                        }
                        setTimeout(function() {
                            $("#addPSAModal").modal("show");
                        }, 250);
                    }
                },
                onAdd: function(event) {
                    var newDate = this.newItem.date;
                    var newResult = this.newItem.result;
                    if (newDate) {
                        var dt = new Date(newDate);
                        var isValid = tnthDates.isValidDefaultDateFormat(newDate);
                        if (!isValid) {
                            this.addErrorMessage = i18next.t("Date must in the valid format.");
                            return false;
                        };
                    }
                    if (isNaN(newResult) || parseInt(newResult) < 0) {
                        this.addErrorMessage = i18next.t("Result must be a valid number.");
                        return false;
                    }
                    this.addErrorMessage = "";
                    var existingItem = $.grep(this.items, function(item) {
                        return item.date == newDate;
                    });
                    if (existingItem.length > 0) {
                        this.newItem.id = existingItem[0].id;
                    }
                    this.postData();
                },
                getData: function() {
                    var self = this;
                    self.loading = true;
                    tnthAjax.getClinical($("#psaTrackerUserId").val(), function(data) {
                        if (data.error) {
                            $("#psaTrackerErrorMessageContainer").html(i18next.t("Error occurred retrieving PSA result data"));
                        } else {
                            if (data.entry) {
                                var results = (data.entry).map(function(item) {
                                    var dataObj = {}, content = item.content, contentCoding = content.code.coding[0];
                                    dataObj.id = content.id;
                                    dataObj.code = contentCoding.code;
                                    dataObj.display = contentCoding.display;
                                    dataObj.updated = tnthDates.formatDateString(item.updated.substring(0,19), "yyyy-mm-dd hh:mm:ss");
                                    dataObj.date = tnthDates.formatDateString(content.issued.substring(0,19), "d M y");
                                    dataObj.result = content.valueQuantity.value;
                                    dataObj.edit = true;
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
                                if (results.length > 10) {
                                    results = results.slice(0, 10);
                                }
                                self.items = results;
                                setTimeout(function() {
                                    self.drawGraph();
                                }, 500);
                                $("#psaTrackerErrorMessageContainer").html("");
                            } else {
                                $("#psaTrackerErrorMessageContainer").html(i18next.t("No result data found"));
                            }
                        }
                        setTimeout(function() {
                            self.loading = false;
                        }, 550);

                    });
                },
                postData: function() {
                    var userId = $("#psaTrackerUserId").val();
                    var cDate = "";
                    var self = this;
                    if (this.newItem.date) {
                        var dt = new Date(this.newItem.date);
                        // in 2017-07-06T12:00:00 format
                        cDate = [dt.getFullYear(), (dt.getMonth()+1), dt.getDate()].join("-");
                        cDate = cDate + "T12:00:00";
                    }
                    var url = '/api/patient/'+userId+'/clinical';
                    var method = "POST";
                    var obsCode = [{ "code": this.clinicalCode, "display": this.clinicalDisplay, "system": this.clinicalSystem }];
                    var obsArray = {};
                    obsArray["resourceType"] = "Observation";
                    obsArray["code"] = {"coding": obsCode};
                    obsArray["issued"] = cDate;
                    obsArray["valueQuantity"] = {"units": "g/dl", "code": "g/dl", "value": this.newItem.result};

                    if (this.newItem.id) {
                        method = "PUT";
                        url = url + "/" + this.newItem.id;
                    }

                    tnthAjax.sendRequest(url, method, userId, {data: JSON.stringify(obsArray)}, function(data) {
                        console.log(data);
                        if (data.error) {
                            self.addErrorMessage = i18next.t("Server error occurred adding PSA result.");
                        }
                        else {
                            $("#addPSAModal").modal("hide");
                            self.getData();
                            self.clearNew();
                            self.addErrorMessage = "";
                        }
                    });
                },
                clearNew: function() {
                    var self = this;
                    for (var prop in self.newItem) {
                        self.newItem[prop] = "";
                    }
                },
                drawGraph: function() {
                    /*
                     * using d3 to draw graph
                     */
                    $("#psaTrackerGraph").html("");
                    var self = this;
                    const WIDTH = 660, HEIGHT = 450, TOP = 50, RIGHT = 10, BOTTOM = 150, LEFT = 60, TIME_FORMAT = "%d %b %Y";

                    // Set the dimensions of the canvas / graph
                    var margin = {top: TOP, right: RIGHT, bottom: BOTTOM, left: LEFT},
                    width = WIDTH - margin.left - margin.right,
                    height = HEIGHT - margin.top - margin.bottom;

                    var timeFormat = d3.time.format(TIME_FORMAT);
                    // Parse the date / time func
                    var parseDate = timeFormat.parse;

                    var data = self.items;

                    data.forEach(function(d) {
                        d.graph_date = parseDate(d.date);
                        d.result = isNaN(d.result)?0:+d.result;
                    });

                    var maxResult = d3.max(data, function(d) {
                        return d.result;
                    });
                    var minResult = d3.min(data, function(d) {
                        return d.result;
                    });

                    var xDomain = d3.extent(data, function(d) { return d.graph_date; });
                    var bound = (width-margin.left-margin.right)/10;
                    var x = d3.time.scale().range([bound, width-bound]);
                    var y = d3.scale.linear().range([height, 0]);

                    function customTickFunc (t0, t1, step) {
                        const day = 1000 * 60 * 60 * 24;
                        var diff = (new Date(t1) - new Date(t0)) / day;
                        var interval = Math.ceil(diff/9);
                        var startTime = new Date(t0),
                            endTime= new Date(t1), times = [];
                        startTime.setUTCDate(startTime.getUTCDate());
                        endTime.setUTCDate(endTime.getUTCDate());
                        while (startTime < endTime && startTime <= endTime) {
                            var dateTime = new Date(startTime);
                            startTime.setUTCDate(startTime.getUTCDate() + interval);
                            var lastInterval = (new Date(startTime) - new Date(endTime)) / day;
                            if (startTime > endTime) {
                                times.push(new Date(endTime));
                                if (lastInterval < interval/2) {
                                    times.push(dateTime);
                                }
                            } else {
                                times.push(dateTime);
                            }
                        }
                        return times;
                    }

                    // Scale the range of the data
                    var endY = Math.max(10, d3.max(data, function(d) { return d.result; }));

                    if (data.length === 1) {
                        var dataArray = [];
                        var firstDate = new Date(data[0].graph_date);
                        xDomain = [data[0].graph_date, new Date(firstDate.setDate(firstDate.getDate() + 365))];
                    }

                    x.domain(xDomain);
                    y.domain([0, endY + (endY/(data.length+1)) ]);

                    // Define the axes
                    var xAxis = d3.svg.axis()
                                .scale(x)
                                .orient("bottom")
                                .ticks(customTickFunc)
                                .tickSize(0, 0, 0)
                                .tickFormat(timeFormat);

                    var yAxis = d3.svg.axis()
                                .scale(y)
                                .orient("left")
                                .tickSize(0, 0, 0)
                                .ticks(10);

                    // Define the line
                    var valueline = d3.svg.line()
                                    .interpolate("linear")
                                    .x(function(d) { return x(d.graph_date); })
                                    .y(function(d) { return y(d.result); });

                    // Adds the svg canvas
                    var svg = d3.select("#psaTrackerGraph")
                                .append("svg")
                                .attr("width", width + margin.left + margin.right)
                                .attr("height", height + margin.top + margin.bottom);
                    //background
                    svg.append("rect")
                        .attr("x", margin.left)
                        .attr("y", margin.top)
                        .attr("width", width)
                        .attr("height", height)
                        .style("stroke", "#777")
                        .style("stroke-width", "1")
                        .style("fill", "#ececec");

                    var graphArea = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");

                    // Add the X Axis
                    graphArea.append("g")
                            .attr("class", "x axis x-axis")
                            .attr("transform", "translate(0," + height + ")")
                            .call(xAxis)
                            .selectAll("text")
                            .attr("y", 0)
                            .attr("x", 7)
                            .attr("dy", ".35em")
                            .attr("transform", "rotate(90)")
                            .attr("class", "axis-stroke")
                            .style("text-anchor", "start");

                    // Add the Y Axis
                    graphArea.append("g")
                            .attr("class", "y axis y-axis")
                            .call(yAxis)
                            .selectAll("text")
                            .attr("dx", "-2px")
                            .attr("dy", "6px")
                            .attr("class","axis-stroke")
                            .style("text-anchor", "end");

                    // add the X gridlines
                    graphArea.append("g")
                            .attr("class", "grid grid-x")
                            .attr("transform", "translate(0," + height + ")")
                            .call(xAxis
                                    .tickSize(-height)
                                    .tickFormat("")
                                );
                    // add the Y gridlines
                    graphArea.append("g")
                            .attr("class", "grid grid-y")
                            .call(yAxis
                                    .tickSize(-width)
                                    .tickFormat("")
                                );

                    // Add the valueline path.
                    graphArea.append("path")
                    .attr("class", "line")
                    .attr("d", valueline(data));


                    // Add the scatterplot
                    graphArea.selectAll("dot")
                            .data(data)
                            .enter().append("circle")
                            .attr("r", 3.7)
                            .attr("class", "circle")
                            .attr("cx", function(d, index) { return x(d.graph_date); })
                            .attr("cy", function(d) { return y(d.result); });

                    // Add caption
                    graphArea.append("text")
                    .attr("x", (width / 2))
                    .attr("y", 0 - (margin.top / 2))
                    .attr("text-anchor", "middle")
                    .attr("class", "graph-caption")
                    .text("PSA (ng/ml)");

                    //add axis legends
                    var xlegend = graphArea.append("g")
                                .attr("transform", "translate(" + (width/2-margin.left+margin.right) + "," + (height + margin.bottom - margin.bottom/3) + ")");

                    xlegend.append("text")
                            .text(i18next.t("PSA Test Date"))
                            .attr("class", "legend-text");

                    var ylegend = graphArea.append("g")
                                .attr("transform", "translate(" + (-margin.left + margin.left/3) + "," + (height/3) + ")")

                    ylegend.append("text")
                        .attr("transform", "rotate(90)")
                        .attr("class", "legend-text")
                        .text(i18next.t("Result (ng/ml)"));

                }
            }
        });
    $(function() {
        psaApp.init();
    });
})();
