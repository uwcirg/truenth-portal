(function() {
  /*
   * a workaround for hiding of loading indicator upon completion of loading of portal wrapper
   * loading indicator needs to continue displaying until patients list has finished loading
   */
  DELAY_LOADING = true;

  function hasValue(val) {return val !== null && val !== "" && val !== "undefined";}
  function showMain() {
    $("#mainHolder").css({
                          "visibility" : "visible",
                          "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
                          "filter": "alpha(opacity=100)",
                          "-moz-opacity": 1,
                          "-khtml-opacity": 1,
                          "opacity": 1
                        });

  }
  // Loading indicator that appears in UI on page loads and when saving
  function showLoader() {
    $("#loadingIndicator").show();
  };

  function __setOrgsMenuHeight(padding) {
    if (!padding) {
      padding = 100;
    };
    var h = parseInt($("#fillOrgs").height());
    if (!isNaN(h) && h > 0) {
      $("#org-menu").height(h + padding);
      if ($("div.admin-table").height() < $("#org-menu").height()) {
        setTimeout( function() { $("div.admin-table").height($("#org-menu").height() + padding);}, 0);
      };
    };
  };

  function __clearFilterButtons() {
    $("#orglist-close-ckbox, #orglist-clearall-ckbox, #orglist-selectall-ckbox").prop("checked", false);
  };

  function AdminTool (userId, identifier, dependencies) {
    this.requestsCounter = 0;
    this.userId = userId;
    this.userOrgs = [];
    this.ajaxRequests = [];
    this.ajaxAborted = false;
    this.arrData = {};
    this.patientsIdList = [];
    this.tableIdentifier = identifier || "patientList";
    this.dependencies = dependencies || {};
    OrgTool.call(this);
  };

  /*
  * extends OrgTool class
  * see OT class definition in main.js should modularize it in the future so it can be instantiated/called safely
  *
  */
  AdminTool.prototype = Object.create(OrgTool.prototype);
  AdminTool.prototype.init = function(callback) {
    if (callback) {
      callback();
    };
  };
  AdminTool.prototype.getDependency = function(key) {
    if (key && this.dependencies.hasOwnProperty(key)) {
      return this.dependencies[key];
    } else {
      /*
       * throw error ? should be visible in console
       */
      throw Error("Dependency " + key + " not found.");
    }
  };
  AdminTool.prototype.fadeLoader = function() {
    DELAY_LOADING = false;
    setTimeout(function() { showMain(); }, 250);
    setTimeout(function() { $("#loadingIndicator").fadeOut(); }, 300);
  };
  AdminTool.prototype.setLoadingMessageVis = function(vis) {
    switch(vis) {
      case "hide":
        $("#adminTable .field-loading-indicator").fadeOut();
        break;
      case "show":
        $("#adminTable .field-loading-indicator").fadeIn();
        break;
    };
  };
  AdminTool.prototype.setStatusLoadingVis = function(vis) {
    switch(vis) {
      case "hide":
        $("#adminTable th.status-field .loading-message-indicator").fadeOut();
        $("#adminTable .bootstrap-table-filter-control-status").css("opacity", 1);
        break;
      case "show":
        $("#adminTable th.status-field .loading-message-indicator").fadeIn();
        break;
    };
  };
  AdminTool.prototype.getPatientsIdList = function() {
    var self = this;
    if (self.patientsIdList.length === 0) {
      var all = $("#adminTable").bootstrapTable("getData");
      if (all) {
        all.forEach(function(o) {
          self.patientsIdList.push(o.id);
        });
      };
    };
    return self.patientsIdList;
  };
  /*
   * currently not being used - client side retrieval of assessment status
   */
  AdminTool.prototype.getData = function(requests, callback) {
      var self = this;
      if (self.ajaxAborted) {
          return false;
      };
      if (!requests || requests.length === 0) {
          return false;
      };
      var userString = requests.shift();
      if (!hasValue(userString)) {
          return false;
      };

      var tnthDates = self.getDependency("tnthDates");
      /*
       *  load the data sequentially
       *  Note, NO concurrent ajax calls here,
       *  one request will wait after the previous one has finished
       */
      var ajaxRequest = $.ajax ({
                                type: "GET",
                                url: "/api/consent-assessment-status",
                                contentType: "application/json; charset=utf-8",
                                data: userString,
                                cache: false,
                                timeout: 5000,
                                beforeSend: function() {
                                  self.setStatusLoadingVis("show");
                                  /*
                                   * disable export functionality while status is being populated
                                   */
                                  $("div.export button").attr("disabled", true);
                                },
                                dataType: "json"
                            }).done(function(data) {
                                  if (data && data.status) {
                                    data.status.forEach(function(status) {
                                        var c = status.consents;
                                        var a = "", s = "", prevItem = {};
                                        if (c) {
                                        c.forEach(function(item) {
                                            if (!item.consent.deleted && (!prevItem.consent_signed || (prevItem.assessment_status != item.assessment_status)
                                                || (String(prevItem.consent_signed).substring(0, 10) != String(item.consent.signed).substring(0, 10)))) {
                                                if (!(/null/.test(item.consent.agreement_url))) {
                                                  var cl = "";
                                                  var sd = tnthDates.formatDateString(item.consent.signed);
                                                  var status = item.assessment_status;
                                                  if (!item.consent.send_reminders) status = "withdrawn";
                                                  switch(String(status).toLowerCase()) {
                                                      case "completed":
                                                        cl = "text-success";
                                                        break;
                                                      case "withdrawn":
                                                        cl = "text-muted";
                                                        break;
                                                      case "due":
                                                        cl = "text-warning";
                                                        break;
                                                      case "overdue":
                                                        cl = "text-danger";
                                                        break;
                                                  };
                                                  a += (a != "" ? "<br/>" : "") + "<span class='" + cl  + " small-text' style='text-transform: capitalize'>" + status + "</span>";
                                                  s += (s != "" ? "<br/>" : "") + sd;
                                                  prevItem.assessment_status = item.assessment_status;
                                                  prevItem.consent_signed = item.consent.signed;
                                                };
                                              };
                                          });
                                      };
                                      if (hasValue(status.user_id)) {
                                        /*
                                         * NOTE, need to get the row data here
                                         * data for all the fields are required for the method, updateByUniqueId
                                         */
                                        var rowData = $("#adminTable").bootstrapTable("getRowByUniqueId", status.user_id);
                                        rowData = rowData || {};
                                        /* update row data with updated assessment status */
                                        rowData["status"] = a;
                                        /* persist data here, help with debugging */
                                        self.arrData[status.user_id] = { id: status.user_id, row: rowData};
                                        $("#adminTable").bootstrapTable("updateByUniqueId", self.arrData[status.user_id]);

                                      };
                                });
                              };
                              if (requests.length > 0) {
                                self.getData(requests, callback);
                              }
                              else {
                                if (callback) {
                                  setTimeout(function() { callback.call(self);}, 300);
                                };
                                self.setStatusLoadingVis("hide");
                                $("div.export button").attr("disabled", false);
                              };
                          }).fail(function(xhr) {
                              self.setStatusLoadingVis("hide");
                              $("div.export button").attr("disabled", false);
                              $("#admin-table-error-message").text("Server error occurred updating row data.  Server error code: " + xhr.status);
                          });
          self.ajaxRequests.push(ajaxRequest);
          return ajaxRequest;
  };
  AdminTool.prototype.updateData = function() {
    /* compile user IDs array from patients list ID */
    var arrUsers = this.getUserIdArray();
    var self = this;
    if (arrUsers.length > 0) {
       self.getData(arrUsers);
    };
  };
  AdminTool.prototype.abortRequests = function(callback, showLoader) {
      var self = this;
     //NEED TO ABORT THE AJAX REQUESTS OTHERWISE CLICK EVENT IS DELAYED DUE TO NETWORK TIE-UP
     if (self.ajaxRequests.length > 0) {
        self.ajaxAborted = true;
        self.ajaxRequests.forEach(function(request, index, array) {

            try {
              if (parseInt(request.readyState) != 4) {
                  /*
                   * aborting the request here to quit immediately, instead of waiting for the
                   * maximum timeout specified
                   */
                  request.timeout = 100;
                  request.abort();
              }
            } catch(e) {
            };
            if (index === array.length - 1) {
              $("#admin-table-error-message").text("");
              if (callback) {
                setTimeout(function() { callback();}, 100);
                if (showLoader) {
                  showLoader();
                };
              };
            };
        });
      } else {
        if (callback) setTimeout(function() { callback();}, 100);
      };

  };
  AdminTool.prototype.getUserIdArray = function(_userIds) {
    var us = "", ct = 0, arrUsers = [];
    if (!_userIds) {
       _userIds = this.getPatientsIdList();
    };
    var max_ct = Math.max(_userIds.length/10, 10);

    for (var index = 0; index < _userIds.length; index++, ct++) {
       us += (us != ""?"&":"") + "user_id=" + _userIds[index];
       if (index === (_userIds.length - 1)) {
         arrUsers.push(us);
       } else if (ct >= max_ct) {
          arrUsers.push(us);
          us = "";
          ct = 0;
       };
    };
    return arrUsers;
  };
  AdminTool.prototype.setUserOrgs = function() {
    var self = this;
    if (hasValue(this.userId)) {
      $.ajax ({
              type: "GET",
              async: false,
              url: "/api/demographics/"+this.userId
      }).done(function(data) {
          if (data && data.careProvider) {
            $.each(data.careProvider,function(i,val){
                var orgID = val.reference.split("/").pop();
                self.userOrgs.push(orgID);
                if (parseInt(orgID) === 0) {
                  $("#createUserLink").attr("disabled", true);
                }
            });
            if (self.userOrgs.length === 0) {
              $("#createUserLink").attr("disabled", true);
            };
          };
      }).fail(function() {

      });
    };
  };
  AdminTool.prototype.getUserOrgs = function() {
    if (this.userOrgs.length === 0) {
      this.setUserOrgs(this.userId);
    };
    return this.userOrgs;
  };
  AdminTool.prototype.initOrgsList = function(requestOrgList, context) {
     
      var self = this;
      //check if the location contains filtered orgs list
      var iterated = /org_list/.test(location.href);
      var noPatientData = $("#admin-table-body").find("tr.no-records-found").length > 0;
      var i18next = self.getDependency("i18next");
      //set user orgs
      self.setUserOrgs();

      $.ajax ({
          type: "GET",
          url: "/api/organization"
      }).done(function(data) {
          /*
           * building an orgs array object for reference later
           */
          self.populateOrgsList(data.entry);
          /*
           * populate orgs dropdown UI
           */
          self.populateUI();

          /*
           * filter orgs UI based on user's orgs
           */
          if (!noPatientData) {
            var hbOrgs = self.getHereBelowOrgs(self.getUserOrgs());
            self.filterOrgs(hbOrgs);
          };

          /*
           * initialize table data
           */
           self.tableData = $("#adminTable").bootstrapTable("getData");

          /*
           * set user's preference for filter(s)
           */
          self.setTableFilters(self.userId);

          var ofields = $("#userOrgs input[name='organization']");
          if (ofields.length > 0) {
            /* attach orgs related events to UI components */
            ofields.each(function() {
              if ((self.getHereBelowOrgs(self.getUserOrgs())).length === 1 ||
                  (iterated && requestOrgList && requestOrgList[$(this).val()])) {
                  $(this).prop("checked", true);
              } else if (self.currentTablePreference) {
               if (self.currentTablePreference.filters) {
                 var fi = self.currentTablePreference.filters;
                 var fa = fi.orgs_filter_control? fi.orgs_filter_control.split(","): null;
                 if (fa) {
                   var oself = $(this), val = oself.val();
                   fa.forEach(function(item) {
                      if (item === val) {
                        oself.prop("checked", true);
                      };
                   });
                  };
               };
             };

            $(this).on("click touchstart", function(e) {
                e.stopPropagation();
                if ($(this).is(":checked")) {
                  var childOrgs = self.getHereBelowOrgs([$(this).val()]);
                  if (childOrgs && childOrgs.length > 0) {
                    childOrgs.forEach(function(org) {
                      $("#userOrgs input[name='organization'][value='" + org + "']").prop("checked", true);
                    });
                  };
                };
                $("#orglist-footer-container input[type='checkbox']").prop("checked", false);
                self.setTablePreference(self.userId, self.tableIdentifier);
                setTimeout(function() { showLoader(); location.reload(); }, 150);
              });
            });

            $("#org-menu").append("<hr><div id='orglist-footer-container'><label><input type='checkbox' id='orglist-selectall-ckbox'>&nbsp;<span class='text-muted'>" + i18next.t("Select All") + "</span></label>&nbsp;&nbsp;&nbsp;<label><input type='checkbox' id='orglist-clearall-ckbox'>&nbsp;<span class='text-muted'>" + i18next.t("Clear All") + "</span></label>&nbsp;&nbsp;&nbsp;<label><input type='checkbox' id='orglist-close-ckbox'>&nbsp;<span class='text-muted'>" + i18next.t("Close") + "</span></label></div>");

            $("#orglist-selectall-ckbox").on("click touchstart", function(e) {
                e.stopPropagation();
                var orgsList = [];
                $("#userOrgs input[name='organization']:visible").each(function() {
                    $(this).prop("checked", true);
                    orgsList.push($(this).val());
                });
                $("#orglist-clearall-ckbox").prop("checked", false);
                $("#orglist-close-ckbox").prop("checked", false);
                /*
                 * pre-set user preference for filtering
                 */
                self.setTablePreference(self.userId, self.tableIdentifier);
                if (orgsList.length > 0) {
                  setTimeout(function() { showLoader(); location.reload(); }, 150);
                };
            });
            $("#orglist-clearall-ckbox").on("click touchstart", function(e) {
                e.stopPropagation();
                self.clearOrgsSelection();
                $("#orglist-selectall-ckbox").prop("checked", false);
                $("#orglist-close-ckbox").prop("checked", false);
                self.setTablePreference(self.userId, self.tableIdentifier);
                setTimeout(function() { showLoader(); location.reload(); }, 150);
            });
            $("#orglist-close-ckbox").on("click touchstart", function(e) {
                e.stopPropagation();
                $("#orglist-selectall-ckbox").prop("checked", false);
                $("#orglist-clearall-ckbox").prop("checked", false);
                $("#orglistSelector").trigger("click");
                return false;
            });
          };
          self.fadeLoader();

      }).fail(function() {
          //console.log("Problem retrieving data from server.");
          $("#org-menu").append("<span class='indent text-danger'>" + i18next.t("Error occurred retrieving data from server.") + "</span>");
          self.fadeLoader();
      });

      //orglist-dropdown
      $("#orglist-dropdown").on("click touchstart", function () {
          setTimeout(function() { __setOrgsMenuHeight(100); __clearFilterButtons(); } , 10);
      });
  };

  AdminTool.prototype.getInstrumentList = function() {
    var iList, tnthAjax = this.getDependency("tnthAjax");
    tnthAjax.getInstrumentsList(true, function(data) {
      if (data && !data.error) {
        iList = data;
      };
    });
    return iList ? iList : false;
  };

  AdminTool.prototype.handleDownloadModal = function() {

      var self = this, i18next = self.getDependency("i18next");
       /*
        *populate instruments list based on user's parent org
        */
      $("#dataDownloadModal").on("shown.bs.modal", function () {
          var instrumentList = self.getInstrumentList();
          if (instrumentList) {
            var parentOrgList = self.getUserTopLevelParentOrgs(self.getUserOrgs());
            if (parentOrgList && parentOrgList.length > 0) {
               var instrumentItems = [];
               parentOrgList.forEach(function(o) {
                  if (instrumentList[o]) {
                    instrumentList[o].forEach(function(n) {
                      instrumentItems.push(n);
                    });
                  };
               });
               if (instrumentItems.length > 0) {
                  $(".instrument-container").hide();
                  var found = false;
                  instrumentItems.forEach(function(item) {
                    if ($("#" + item + "_container").length > 0) {
                      $("#" + item + "_container").show();
                      found = true;
                    };
                  });
                  if (!found) {
                    $(".instrument-container").show();
                  };
               };
            };
          };
          $("#patientsInstrumentList").addClass("ready");
      });
      /*
       * attach on click event to submit button in the download modal
       */
      $(document).delegate("#patientsDownloadButton", "click", function(event){
        var instruments = "", dataType = "";
        $("input[name='instrument'").each(function() {
            if ($(this).is(":checked")) {
              instruments += (instruments !== "" ? "&": "") + "instrument_id="+$(this).val();
            };
        });
        $("input[name='downloadType']").each(function() {
            if ($(this).is(":checked")) {
              dataType = $(this).val();
            };
        });
        if (instruments !== "" && dataType !== "") {
            //alert(instruments)
            $("#_downloadMessage").text("");
            $("#_downloadLink").attr("href", "/api/patient/assessment?" + instruments + "&format=" + dataType);
            $("#_downloadLink")[0].click();
        } else {
            var message = (instruments === "" ? i18next.t("Please choose at least one instrument."): "");
            if (dataType === "") {
              message += (message !== "" ? "<br/>": "") + i18next.t("Please choose one download type.");
            };
            $("#_downloadMessage").html(message);
        };
      });

      /*
       * attach event to each checkbox in the download instruments modal
       */
      $("input[name='instrument'], input[name='downloadType']").on("click", function() {
          if ($(this).is(":checked")) {
            $("#_downloadMessage").text("");
          };
      });
  };
  AdminTool.prototype.clearOrgsSelection = function() {
    $("#userOrgs input[name='organization']").each(function() {
        $(this).prop("checked", false);
    });
  };
  /*
   * client side filtering of table rows by orgs
   * NOT Recommended for use on large tables
   * performance presents an issue
   */
  AdminTool.prototype.filterTableByOrgs = function() {
    var d = this.tableData || $("#adminTable").bootstrapTable("getData");
    var checkedOrgs = $("#userOrgs input[name='organization']:checked");
    if (checkedOrgs.length > 0) {
      var d2 = $.grep(d, function(item,i) {
        var found = false;
        checkedOrgs.each(function() {
          if (!found) {
              var r = new RegExp($(this).val() + "");
              //console.log("val, item, found ", $(this).val(), item.organization, r.test(item.organization))
              if (r.test(item.organization)) {
                found = true;
              };
          };
        });
        return found;
      });
      (function(d2) {
        setTimeout(function() { $('#adminTable').bootstrapTable("load", d2); }, 300);
      })(d2);
    } else {
      setTimeout(function() { $("#adminTable").bootstrapTable("load", d); }, 300);
    };
  };
  AdminTool.prototype.getDefaultTablePreference = function() {
    return {sort_field: "id",sort_order: "desc"};
  };
  AdminTool.prototype.getTablePreference = function(userId, tableName, setFilter, setColumnSelections) {
      if (this.currentTablePreference) {
        return this.currentTablePreference;
      };
      var prefData = null,
          self = this,
          uid = userId||self.userId,
          tableIdentifier = tableName||self.tableIdentifier,
          tnthAjax = self.getDependency("tnthAjax");

      tnthAjax.getTablePreference(uid, tableIdentifier, {"sync": true}, function(data) {
        if (data && !data.error) {
          prefData = data || self.getDefaultTablePreference();
          self.currentTablePreference = prefData;
        };
        //set filter values
        if (setFilter) {
          self.setTableFilters(uid);
        };
        //set column selection(s)
        if (setColumnSelections) {
          self.setColumnSelections();
        };
      });
      return prefData;
  };

  AdminTool.prototype.setColumnSelections = function() {
    var prefData = this.getTablePreference(this.userId, this.tableIdentifier);
    if (prefData && prefData.filters && prefData.filters.column_selections) {
        var visibleColumns = $("#adminTable").bootstrapTable("getVisibleColumns");
        /*
         * hide visible columns
         */
        visibleColumns.forEach(function(c) {
          $("#adminTable").bootstrapTable("hideColumn", c.field);
        });
        /*
         * show column(s) based on preference
         */
        prefData.filters.column_selections.forEach(function(column) {
            $(".fixed-table-toolbar input[type='checkbox'][data-field='" + column + "']").prop("checked", true);
            $("#adminTable").bootstrapTable("showColumn", column);
        });
    };
  };

  AdminTool.prototype.setTableFilters = function(userId) {
      var prefData = null, tnthAjax = this.getDependency("tnthAjax");
      if (this.currentTablePreference) {
        prefData = this.currentTablePreference;
      } else {
        tnthAjax.getTablePreference(userId||this.userId, this.tableIdentifier, {"sync": true}, function(data) {
          if (data && !data.error) {
            prefData = data;
           };
        });
      };
      if (prefData) {
         //set filter values
        if (prefData.filters) {
          for (var item in prefData.filters) {
            var fname = "#adminTable .bootstrap-table-filter-control-"+item;
            /*
             * note this is based on the trigger event for filtering specify in the plugin
             */
            if ($(fname).length > 0) $(fname).val(prefData.filters[item]).trigger($(fname).attr("type") === "text" ? "keyup": "change");
          };
        };
      };
  };

  AdminTool.prototype.setTablePreference = function(userId, tableName, sortField, sortOrder, filters) {
    var tnthAjax = this.getDependency("tnthAjax");
    tableName = tableName || this.tableIdentifier;

    if (hasValue(tableName)) {
      var data = {};
      if (hasValue(sortField) && hasValue(sortOrder)) {
        data["sort_field"] = sortField;
        data["sort_order"] = sortOrder;
      } else {
      	//get selected sorted field information on UI
      	var sortedField = $("#adminTable th[data-field]").has(".sortable.desc, .sortable.asc");
      	if (sortedField.length > 0) {
      		data["sort_field"] = sortedField.attr("data-field");
      		var sortedOrder = "desc";
      		sortedField.find(".sortable").each(function() {
      			if ($(this).hasClass("desc")) sortedOrder = "desc";
      			else if ($(this).hasClass("asc")) sortedOrder = "asc";
      		});
      		data["sort_order"] = sortedOrder;
      	} else {
  	    	//It is possible the table is not sorted yet so get the default
  	    	var defaultPref = this.getDefaultTablePreference();
  	    	data["sort_field"] = defaultPref.sort_field;
  	    	data["sort_order"] = defaultPref.sort_order;
  	    };
      }
      var __filters = filters || {};

      //get fields
      if (Object.keys(__filters).length === 0) {
        $("#adminTable .filterControl select, #adminTable .filterControl input").each(function() {
        	if (hasValue($(this).val())) {
        		var field = $(this).closest("th").attr("data-field");
        		__filters[field] = $(this).get(0).nodeName.toLowerCase() === "select" ? $(this).find("option:selected").text(): $(this).val();
        	};
        });
      };
      /*
       * get selected orgs from the filter list by site control
       */
      var selectedOrgs = "";
      $("#userOrgs input[name='organization']:checked").each(function() {
        selectedOrgs += (hasValue(selectedOrgs) ? ",": "") + $(this).val();
      });
      if (hasValue(selectedOrgs)) __filters["orgs_filter_control"] = selectedOrgs;
      else __filters["orgs_filter_control"] = "";

      /*
       * get column selections
       */
       __filters["column_selections"] = [];
      $(".fixed-table-toolbar input[type='checkbox'][data-field]:checked").each(function() {
        __filters["column_selections"].push($(this).attr("data-field"));
      });


      data["filters"] = __filters;

      if (Object.keys(data).length > 0) {
        tnthAjax.setTablePreference(userId||this.userId, tableName, {"data": JSON.stringify(data)});
        this.currentTablePreference = data;
      };
    };
  };

  AdminTool.prototype.getReportModal = function(patientId) {

    $("#patientReportModal").modal("show");
    $("#patientReportLoader").removeClass("tnth-hide");

    var self = this;
    var tnthDates = self.getDependency("tnthDates"), tnthAjax = self.getDependency("tnthAjax"), i18next = self.getDependency("i18next");

    tnthAjax.patientReport(patientId, function(data) {
        if (data) {
          if (!data.error) {
              if (data["user_documents"] && data["user_documents"].length > 0) {
                var existingItems = {}, count = 0;
                /*
                 * sort to get the latest first
                 */
                var documents = data["user_documents"].sort(function(a,b){
                   return new Date(b.uploaded_at) - new Date(a.uploaded_at);
                });
                var content = "<table class='table-bordered table-condensed table-responsive tnth-table'>";
                content += "<TH>" + i18next.t("Type") + "<TH>"+ i18next.t("Report Name") + "</TH><TH>" + i18next.t("Generated (GMT)") + "</TH><TH>" + i18next.t("Downloaded") + "</TH>";
                documents.forEach(function(item) {

                    var c = item["contributor"];

                    /*
                     * only draw the most recent, same report won't be displayed
                     */
                    if (!existingItems[c] && hasValue(c)) {
                      content += "<tr>" +
                                "<td>" + c + "</td>" +
                                "<td>" + item["filename"] + "</td>" +
                                "<td>" + tnthDates.formatDateString(item["uploaded_at"], "iso") + "</td>" +
                                "<td class='text-center'>" + '<a title="' + i18next.t("Download") + '" href="' + '/api/user/' + String(item["user_id"]) + '/user_documents/' + String(item["id"])+ '"><i class="fa fa-download"></i></a>' + "</td>"
                                "</tr>";
                      existingItems[c] = true;
                      count++;
                    };
                });
                content += "</table>";
                content += "<br/>";
                content += "<a class='btn btn-tnth-primary btn-sm btn-all'>" + i18next.t("View All") + "</a>";

                $("#patientReportContent").html(content);
                if (count > 1) $("#patientReportModal .modal-title").text(i18next.t("Patient Reports"));
                else $("#patientReportModal .modal-title").text(i18next.t("Patient Report"));
                $("#patientReportContent .btn-all").attr("href", "patient_profile/"+patientId+"#profilePatientReportTable");

              } else {
                $("#patientReportMessage").html(i18next.t("No report data found."));
              };

            } else $("#patientReportMessage").html(i18next.t("Error occurred retrieving patient report"));
          };
        $("#patientReportLoader").addClass("tnth-hide");
    });
  };

  AdminTool.prototype.rowLinkEvent = function () {
    $("#admin-table-body.data-link").delegate("tr", "click", function(e) {
        if (e.target && (e.target.tagName.toLowerCase() != "td")) {
          if (e.target.tagName.toLowerCase() === "a" && e.target.click) {
            return;
          };
        };
        e.preventDefault();
        e.stopPropagation();
        var row = $(this).closest("tr");
        if (!row.hasClass("no-records-found")) {
          document.location = $(this).closest("tr").attr("data-link");
        };
    });
  };

  if (window.portal == null) {
    window.portal = {};
  };

  window.portal.AdminTool = AdminTool;

})();


