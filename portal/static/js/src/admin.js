import tnthAjax from "./modules/TnthAjax.js";
import tnthDates from "./modules/TnthDate.js";
import Utility from "./modules/Utility.js";
import CurrentUser from "./mixins/CurrentUser.js";
import {
  EPROMS_MAIN_STUDY_ID,
  EPROMS_SUBSTUDY_ID,
} from "./data/common/consts.js";

(function () {
  /*global Vue DELAY_LOADING i18next $ */
  var DELAY_LOADING = true; //a workaround for hiding of loading indicator upon completion of loading of portal wrapper - loading indicator needs to continue displaying until patients list has finished loading
  $.ajaxSetup({
    contentType: "application/json; charset=utf-8",
  });
  var AdminObj = (window.AdminObj = new Vue({
    el: "#adminTableContainer",
    errorCaptured: function (Error, Component, info) {
      console.error(
        "Error: ",
        Error,
        " Component: ",
        Component,
        " Message: ",
        info
      ); /* console global */
      this.setContainerVis();
      return false;
    },
    errorHandler: function (err, vm) {
      this.dataError = true;
      var errorElement = document.getElementById("admin-table-error-message");
      if (errorElement) {
        errorElement.innerHTML =
          "Error occurred initializing Admin Vue instance.";
      }
      console.warn("Admin Vue instance threw an error: ", vm, this);
      console.error("Error thrown: ", err);
      this.setContainerVis();
    },
    created: function () {
      this.injectDependencies();
    },
    mounted: function () {
      var self = this;
      Utility.VueErrorHandling(); /* global VueErrorHandling */
      this.preConfig(function () {
        if ($("#adminTable").length > 0) {
          self.setLoaderContent();
          self.rowLinkEvent();
          self.initToggleListEvent();
          self.initExportReportDataSelector();
          self.initTableEvents();
          self.handleDeletedUsersVis();
          self.setRowItemEvent();
          self.handleAffiliatedUIVis();
          if (self.userId) {
            self.handleCurrentUser();
            // self.setColumnSelections();
            // self.setTableFilters(self.userId); //set user's preference for filter(s)
          }
          setTimeout(function () {
            self.setContainerVis();
          }, 350);
        } else {
          self.handleCurrentUser();
        }
      });
    },
    mixins: [CurrentUser],
    data: {
      dataError: false,
      configured: false,
      initIntervalId: 0,
      sortFilterEnabled: false,
      showDeletedUsers: false,
      orgsSelector: {
        selectAll: false,
        clearAll: false,
        close: false,
      },
      ROW_ID_PREFIX: "data_row_",
      ROW_ID: "userid",
      tableIdentifier: "adminList",
      popoverEventInitiated: false,
      dependencies: {},
      tableConfig: {
        formatShowingRows: function (pageFrom, pageTo, totalRows) {
          var rowInfo;
          setTimeout(function () {
            rowInfo = i18next
              .t("Showing {pageFrom} to {pageTo} of {totalRows} users")
              .replace("{pageFrom}", pageFrom)
              .replace("{pageTo}", pageTo)
              .replace("{totalRows}", totalRows);
            $(".pagination-detail .pagination-info").html(rowInfo);
          }, 10);
          return rowInfo;
        },
        formatRecordsPerPage: function (pageNumber) {
          return i18next
            .t("{pageNumber} records per page")
            .replace("{pageNumber}", pageNumber);
        },
        formatToggle: function () {
          return i18next.t("Toggle");
        },
        formatColumns: function () {
          return i18next.t("Columns");
        },
        formatAllRows: function () {
          return i18next.t("All rows");
        },
        formatSearch: function () {
          return i18next.t("Search");
        },
        formatNoMatches: function () {
          return i18next.t("No matching records found");
        },
        formatExport: function () {
          return i18next.t("Export data");
        },
      },
      currentTablePreference: null,
      errorCollection: {
        orgs: "",
        demo: "",
      },
      patientReports: {
        data: [],
        message: "",
        loading: false,
      },
      exportReportTimeoutID: 0,
      exportReportProgressTime: 0,
      arrExportReportTimeoutID: [],
      exportDataType: "",
    },
    methods: {
      injectDependencies: function () {
        var self = this;
        window.portalModules =
          window.portalModules ||
          {}; /*eslint security/detect-object-injection: off */
        window.portalModules["tnthAjax"] = tnthAjax;
        window.portalModules["tnthDates"] = tnthDates;
        for (var key in window.portalModules) {
          if ({}.hasOwnProperty.call(window.portalModules, key)) {
            self.dependencies[key] = window.portalModules[key];
          }
        }
      },
      getDependency: function (key) {
        if (key && this.dependencies.hasOwnProperty(key)) {
          return this.dependencies[key];
        } else {
          throw Error("Dependency " + key + " not found."); //throw error ? should be visible in console
        }
      },
      setLoaderContent: function () {
        $("#adminTableContainer .fixed-table-loading").html("");
      },
      setContainerVis: function () {
        $("#adminTableContainer").addClass("active");
        this.fadeLoader();
      },
      showMain: function () {
        $("#mainHolder").css({
          visibility: "visible",
          "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
          filter: "alpha(opacity=100)",
          "-moz-opacity": 1,
          "-khtml-opacity": 1,
          opacity: 1,
        });
      },
      handleCurrentUser: function () {
        var self = this;
        this.initCurrentUser(function () {
          self.onCurrentUserInit();
        }, true);
      },
      isSubStudyPatientView: function () {
        return $("#patientList").hasClass("substudy");
      },
      allowSubStudyView: function () {
        return this.userResearchStudyIds.indexOf(EPROMS_SUBSTUDY_ID) !== -1;
      },
      setSubStudyUIElements: function () {
        if (this.allowSubStudyView()) {
          $("#patientList .eproms-substudy").removeClass("tnth-hide").show();
          return;
        }
        $("#patientList .eproms-substudy").hide();
      },
      getExportReportUrl: function () {
        let dataType = this.exportDataType || "json";
        let researchStudyID = this.isSubStudyPatientView()
          ? EPROMS_SUBSTUDY_ID
          : EPROMS_MAIN_STUDY_ID;
        return `/api/report/questionnaire_status?research_study_id=${researchStudyID}&format=${dataType}`;
      },
      clearExportReportTimeoutID: function () {
        if (!this.arrExportReportTimeoutID.length) {
          return false;
        }
        let self = this;
        for (
          var index = 0;
          index < self.arrExportReportTimeoutID.length;
          index++
        ) {
          clearTimeout(self.arrExportReportTimeoutID[index]);
        }
      },
      onBeforeExportReportData: function () {
        $("#exportReportContainer").removeClass("open").popover("show");
        $("#btnExportReport").attr("disabled", true);
        $(".exportReport__status").addClass("active");
        this.clearExportReportTimeoutID();
        this.exportReportProgressTime = new Date();
        let pastInfo = this.getCacheReportInfo();
        if (pastInfo) {
          $(".exportReport__history").html(
            `<a href="${pastInfo.url}" target="_blank">${i18next
              .t("View last result exported on {date}")
              .replace(
                "{date}",
                tnthDates.formatDateString(pastInfo.date, "iso")
              )}</a>`
          );
        }
      },
      onAfterExportReportData: function (options) {
        options = options || {};
        $("#btnExportReport").attr("disabled", false);
        $(".exportReport__status").removeClass("active");
        if (options.error) {
          this.updateProgressDisplay("", "");
          $(".exportReport__error .message").html(
            `Request to export report data failed.${
              options.message ? "<br/>" + options.message : ""
            }`
          );
          $(".exportReport__retry").removeClass("tnth-hide");
          this.clearExportReportTimeoutID();
          return;
        }
        $("#exportReportContainer").popover("hide");
        $(".exportReport__error .message").html("");
        $(".exportReport__retry").addClass("tnth-hide");
      },
      initToggleListEvent: function () {
        if (!$("#patientListToggle").length) return;
        $("#patientListToggle a").on("click", (e) => {
          e.preventDefault();
        });
        $("#patientListToggle .radio, #patientListToggle .label").on(
          "click",
          function (e) {
            e.stopImmediatePropagation();
            $("#patientListToggle").addClass("loading");
            setTimeout(
              function () {
                window.location = $(this).closest("a").attr("href");
              }.bind(this),
              50
            );
          }
        );
      },
      initExportReportDataSelector: function () {
        let self = this;
        tnthAjax.getConfiguration(this.userId, false, function (data) {
          if (
            !data ||
            !data.PATIENT_LIST_ADDL_FIELDS ||
            data.PATIENT_LIST_ADDL_FIELDS.indexOf("status") === -1
          ) {
            $("#exportReportContainer").hide();
            return false;
          }
          let html = $("#exportReportPopoverWrapper").html();
          $("#adminTableContainer .fixed-table-toolbar .columns-right").append(
            html
          );
          $("#exportReportContainer").attr(
            "data-content",
            $("#exportReportPopoverContent").html()
          );
          $("#exportReportContainer .data-types li").each(function () {
            $(this).attr("title", self.getExportReportUrl());
          });
          $("#exportReportContainer").on("shown.bs.popover", function () {
            $(".exportReport__retry")
              .off("click")
              .on("click", function (e) {
                e.stopImmediatePropagation();
                $("#exportReportContainer").popover("hide");
                setTimeout(function () {
                  $("#btnExportReport").trigger("click");
                }, 50);
              });
          });
          $("#exportReportContainer").on("hide.bs.popover", function () {
            self.clearExportReportTimeoutID();
          });
          $("#exportReportContainer .data-types li").on("click", function (e) {
            e.stopPropagation();
            self.exportDataType = $(this).attr("data-type");
            let reportUrl = self.getExportReportUrl();
            self.updateProgressDisplay("", "");
            $.ajax({
              type: "GET",
              url: reportUrl,
              beforeSend: function () {
                self.onBeforeExportReportData();
              },
              success: function (data, status, request) {
                let statusUrl = request.getResponseHeader("Location");
                self.updateExportProgress(statusUrl, function (data) {
                  self.onAfterExportReportData(data);
                });
              },
              error: function (xhr) {
                self.onAfterExportReportData({
                  error: true,
                  message: xhr.responseText,
                });
              },
            });
          });
          $("#adminTableContainer .columns-right .export button").attr(
            "title",
            i18next.t("Export patient list")
          );
        });
      },
      updateProgressDisplay: function (status, percentage, showLoader) {
        $(".exportReport__percentage").text(percentage);
        $(".exportReport__status").text(status);
        if (showLoader) {
          $(".exportReport__loader").removeClass("tnth-hide");
        } else {
          $(".exportReport__loader").addClass("tnth-hide");
        }
      },
      setCacheReportInfo: function (resultUrl) {
        if (!resultUrl) return false;
        localStorage.setItem(
          "exportReportInfo_" + this.userId + "_" + this.exportDataType,
          JSON.stringify({
            date: new Date(),
            url: resultUrl,
          })
        );
      },
      getCacheReportInfo: function () {
        let cachedItem = localStorage.getItem(
          "exportReportInfo_" + this.userId + "_" + this.exportDataType
        );
        if (!cachedItem) return false;
        return JSON.parse(cachedItem);
      },
      updateExportProgress: function (statusUrl, callback) {
        callback = callback || function () {};
        if (!statusUrl) {
          callback({ error: true });
          return;
        }
        let self = this;
        // send GET request to status URL
        let rqId = $.getJSON(statusUrl, function (data) {
          if (!data) {
            callback({ error: true });
            return;
          }
          let percent = "0%",
            exportStatus = data["state"].toUpperCase();
          if (data["current"] && data["total"] && parseInt(data["total"]) > 0) {
            percent = parseInt((data["current"] * 100) / data["total"]) + "%";
          }
          //update status and percentage displays
          self.updateProgressDisplay(exportStatus, percent, true);
          let arrIncompleteStatus = ["PENDING", "PROGRESS", "STARTED"];
          if (arrIncompleteStatus.indexOf(exportStatus) === -1) {
            if (exportStatus === "SUCCESS") {
              setTimeout(
                function () {
                  let resultUrl = statusUrl.replace("/status", "");
                  self.setCacheReportInfo(resultUrl);
                  window.location.assign(resultUrl);
                }.bind(self),
                50
              ); //wait a bit before retrieving results
            }
            self.updateProgressDisplay(data["state"], "");
            setTimeout(function () {
              callback(exportStatus === "SUCCESS" ? data : { error: true });
            }, 300);
          } else {
            //check how long the status stays in pending
            if (exportStatus === "PENDING") {
              let passedTime =
                (new Date().getTime() -
                  self.exportReportProgressTime.getTime()) /
                1000;
              if (passedTime > 300) {
                //more than 5 minutes passed and the task is still in PENDING status
                //never advanced to PROGRESS to start the export process
                //abort
                self.onAfterExportReportData({
                  error: true,
                  message: i18next.t(
                    "More than a minute spent in pending status."
                  ),
                });
                return;
              }
            }
            // rerun in 2 seconds
            self.exportReportTimeoutID = setTimeout(
              function () {
                self.updateExportProgress(statusUrl, callback);
              }.bind(self),
              2000
            ); //each update invocation should be assigned a unique timeoutid
            self.arrExportReportTimeoutID.push(self.exportReportTimeoutID);
          }
        }).fail(function (xhr) {
          callback({ error: true, message: xhr.responseText });
        });
      },
      onCurrentUserInit: function () {
        if (this.userOrgs.length === 0) {
          $("#createUserLink").attr("disabled", true);
        }
        this.handleDisableFields();
        if (this.hasOrgsSelector()) {
          this.initOrgsFilter();
          this.initOrgsEvent();
        }
        this.setSubStudyUIElements();
        this.initRoleBasedEvent();
        this.fadeLoader();
        setTimeout(
          function () {
            this.setOrgsFilterWarning();
          }.bind(this),
          650
        );
      },
      setOrgsMenuHeight: function (padding) {
        padding = padding || 85;
        var h = parseInt($("#fillOrgs").height());
        if (h > 0) {
          var adminTable = $("div.admin-table"),
            orgMenu = $("#org-menu");
          var calculatedHeight = h + padding;
          $("#org-menu").height(calculatedHeight);
          if (adminTable.height() < orgMenu.height()) {
            setTimeout(function () {
              adminTable.height(orgMenu.height() + calculatedHeight);
            }, 0);
          }
        }
      },
      clearFilterButtons: function () {
        this.setOrgsSelector({
          selectAll: false,
          clearAll: false,
          close: false,
        });
      },
      fadeLoader: function () {
        var self = this;
        self.showMain();
        setTimeout(function () {
          $("body").removeClass("vis-on-callback");
          $("#loadingIndicator").fadeOut().css("visibility", "hidden");
        }, 150);
      },
      showLoader: function () {
        $("#loadingIndicator").show().css("visibility", "visible");
      },
      preConfig: function (callback) {
        var self = this,
          tnthAjax = this.getDependency("tnthAjax");
        callback = callback || function () {};
        tnthAjax.getCurrentUser(
          function (data) {
            if (data) {
              self.userId = data.id;
              self.setIdentifier();
              self.setSortFilterProp();
              self.configTable();
              self.configured = true;
              setTimeout(function () {
                callback();
              }, 50);
            } else {
              alert(i18next.t("User Id is required")); /* global i18next */
              self.configured = true;
              return false;
            }
          },
          {
            sync: true,
          }
        );
      },
      setIdentifier: function () {
        var adminTableContainer = $("#adminTableContainer");
        if (adminTableContainer.hasClass("patient-view")) {
          this.tableIdentifier = "patientList";
        }
        if (adminTableContainer.hasClass("staff-view")) {
          this.tableIdentifier = "staffList";
        }
        if (adminTableContainer.hasClass("substudy")) {
          this.tableIdentifier = "substudyPatientList";
        }
      },
      setOrgsSelector: function (obj) {
        if (!obj) {
          return false;
        }
        var self = this;
        for (var prop in obj) {
          if (self.orgsSelector.hasOwnProperty(prop)) {
            self.orgsSelector[prop] = obj[prop];
          }
        }
      },
      setSortFilterProp: function () {
        this.sortFilterEnabled =
          this.tableIdentifier === "patientList" ||
          this.tableIdentifier === "substudyPatientList";
      },
      configTable: function () {
        var options = {};
        var sortObj = this.getTablePreference(
          this.userId,
          this.tableIdentifier
        );
        sortObj = sortObj || this.getDefaultTablePreference();
        options.sortName = sortObj.sort_field;
        options.sortOrder = sortObj.sort_order;
        options.filterBy = sortObj;
        options.exportOptions = {
          /* global Utility getExportFileName*/
          fileName: Utility.getExportFileName(
            $("#adminTableContainer").attr("data-export-prefix")
          ),
        };
        $("#adminTable").bootstrapTable(this.getTableConfigOptions(options));
      },
      getTableConfigOptions: function (options) {
        if (!options) {
          return this.tableConfig;
        }
        return $.extend({}, this.tableConfig, options);
      },
      initRoleBasedEvent: function () {
        let self = this;
        if (this.isAdminUser()) {
          /* turn on test account toggle checkbox if admin user */
          $("#frmTestUsersContainer").removeClass("tnth-hide");
          $("#include_test_role").on("click", function () {
            $("#adminTable").bootstrapTable("refresh");
          });
        }
      },
      handleDeletedAccountRows: function (tableData) {
        const rows = tableData && tableData.rows ? tableData.rows : [];
        const self = this;
        $("#adminTable tbody tr").each(function () {
          const rowId = $(this).attr("data-uniqueid");
          const isDeleted = rows.find(
            (o) => parseInt(o[self.ROW_ID]) === parseInt(rowId) && o.deleted
          );
          if (!!isDeleted) {
            $(this).addClass("deleted-user-row");
          }
        });
      },
      handleDateFields: function (tableData) {
        const rows = tableData && tableData.rows ? tableData.rows : [];
        const self = this;
        $("#adminTable tbody tr").each(function () {
          const rowId = $(this).attr("data-uniqueid");
          const matchedRow = rows.find(
            (o) => parseInt(o[self.ROW_ID]) === parseInt(rowId)
          );
          if (matchedRow) {
            $(this)
              .find(".birthdate-field")
              .text(
                tnthDates.getDateWithTimeZone(matchedRow.birthdate, "d M y")
              );
            $(this)
              .find(".consentdate-field")
              .text(
                tnthDates.getDateWithTimeZone(matchedRow.consentdate, "d M y")
              );
          }
        });
      },
      initTableEvents: function () {
        var self = this;
        $("#adminTable").on("post-body.bs.table", function () {
          self.setContainerVis();
        });
        $("#adminTable").on("load-success.bs.table", function (e, data) {
          self.setColumnSelections();
          self.addFilterPlaceHolders();
          self.setTableFilters(self.userId); //set user's preference for filter(s)
          self.handleDeletedAccountRows(data);
          self.handleDateFields(data);
        });
        $("#adminTable").on("reset-view.bs.table", function () {
          self.addFilterPlaceHolders();
          self.resetRowVisByActivationStatus();
          self.setRowItemEvent();
        });
        $("#adminTable").on("search.bs.table", function () {
          self.resetRowVisByActivationStatus();
          self.setRowItemEvent();
        });
        $("#adminTable").on(
          "click-row.bs.table",
          function (e, row, $element, field) {
            e.stopPropagation();
            if (row.deleted) return;
            window.location =
              "/patients/patient_profile/" + $element.attr("data-uniqueid");
          }
        );
        $(window).bind("scroll mousedown mousewheel keyup", function () {
          if ($("html, body").is(":animated")) {
            $("html, body").stop(true, true);
          }
        });
        $("#chkDeletedUsersFilter").on("click", function () {
          self.handleDeletedUsersVis();
        });
        if (this.sortFilterEnabled) {
          $("#adminTable")
            .on("sort.bs.table", function (e, name, order) {
              self.setTablePreference(
                self.userId,
                self.tableIdentifier,
                name,
                order
              );
            })
            .on("column-search.bs.table", function () {
              self.setTablePreference(self.userId);
            })
            .on("column-switch.bs.table", function () {
              self.setTablePreference(self.userId);
            });
        }
        $("#adminTableToolbar .orgs-filter-warning").popover();
        $("#adminTable .filterControl select").on("change", function () {
          if ($(this).find("option:selected").val()) {
            $(this).addClass("active");
            return;
          }
          $(this).removeClass("active");
        });
        $("#adminTable .filterControl input").on("change", function () {
          if ($(this).val()) {
            $(this).addClass("active");
            return;
          }
          $(this).removeClass("active");
        });
      },
      allowDeletedUserFilter: function () {
        return $("#chkDeletedUsersFilter").length;
      },
      setShowDeletedUsersFlag: function () {
        if (!this.allowDeletedUserFilter()) {
          return;
        }
        this.showDeletedUsers = $("#chkDeletedUsersFilter").is(":checked");
      },
      handleDeletedUsersVis: function () {
        if (!this.allowDeletedUserFilter()) {
          return;
        }
        this.setShowDeletedUsersFlag();
        if (this.showDeletedUsers) {
          $("#adminTable").bootstrapTable("filterBy", {
            activationstatus: "deactivated",
          });
        } else {
          $("#adminTable").bootstrapTable("filterBy", {
            activationstatus: "activated",
          });
        }
      },
      handleAffiliatedUIVis: function () {
        $(
          "#adminTableContainer input[data-field='id']:checkbox, #adminTableContainer input[data-field='deactivate']:checkbox, #adminTableContainer input[data-field='activationstatus']:checkbox"
        )
          .closest("label")
          .hide(); //hide checkbox for hidden id field and deactivate account field from side menu
        $("#patientReportModal").modal({
          show: false,
        });
      },
      setRowItemEvent: function () {
        var self = this;
        $("#adminTableContainer .btn-report")
          .off("click")
          .on("click", function (e) {
            e.stopPropagation();
            if ($(this).closest(".deleted-user-row").length) {
              //prevent viewing of report for deleted users
              return false;
            }
            self.getReportModal($(this).attr("data-patient-id"), {
              documentDataType: $(this).attr("data-document-type"),
            });
          });
        $("#adminTableContainer [name='chkRole']").each(function () {
          $(this)
            .off("click")
            .on("click", function (e) {
              e.stopPropagation();
              var userId = $(this).attr("data-user-id");
              if (!userId) {
                return false;
              }
              var role = $(this).attr("data-role"),
                checked = $(this).is(":checked"),
                tnthAjax = self.getDependency("tnthAjax");
              $("#loadingIndicator_" + userId).show();
              $("#" + self.ROW_ID_PREFIX + userId).addClass("loading");
              tnthAjax.getRoles(userId, function (data) {
                if (!data || data.error) {
                  $("#loadingIndicator_" + userId).hide();
                  $("#" + self.ROW_ID_PREFIX + userId).removeClass("loading");
                  alert(i18next.t("Error occurred retrieving roles for user"));
                  return false;
                }
                var arrRoles = data.roles;
                arrRoles = $.grep(arrRoles, function (item) {
                  return (
                    String(item.name).toLowerCase() !==
                    String(role).toLowerCase()
                  );
                });
                if (checked) {
                  arrRoles = arrRoles.concat([{ name: role }]);
                }
                tnthAjax.putRoles(
                  userId,
                  { roles: arrRoles },
                  "",
                  function (data) {
                    $("#loadingIndicator_" + userId).hide();
                    $("#" + self.ROW_ID_PREFIX + userId).removeClass("loading");
                    if (data.error) {
                      alert(i18next.t("Error occurred updating user roles"));
                      return false;
                    }
                  }
                );
              });
            });
        });
        $("#adminTableContainer .btn-delete-user").each(function () {
          $(this).popover({
            container: "#adminTable",
            html: true,
            content: [
              "<div>{title}</div>",
              "<div class='buttons-container'>",
              "<button class='btn btn-small btn-default popover-btn-deactivate' data-user-id='{userid}'>{yes}</button>&nbsp;",
              "<button class='btn btn-small btn-default popover-btn-cancel'>{no}</button>",
              "</div>",
            ]
              .join("")
              .replace(
                "{title}",
                i18next.t("Are you sure you want to deactivate this account?")
              )
              .replace(/\{userid\}/g, $(this).attr("data-user-id"))
              .replace("{yes}", i18next.t("Yes"))
              .replace("{no}", i18next.t("No")),
            placement: "top",
          });
          $(this)
            .off("click")
            .on("click", function (e) {
              e.stopPropagation();
              $(this).popover("show");
              var userId = $(this).attr("data-user-id");
              if (!$("#data-delete-loader-" + userId).length) {
                $(this)
                  .parent()
                  .append(
                    '<i id="data-delete-loader-{userid}" class="fa fa-spinner tnth-hide"></i>'.replace(
                      "{userid}",
                      userId
                    )
                  );
              }
            });
        });
        $(document)
          .undelegate(".popover-btn-deactivate", "click")
          .on("click", ".popover-btn-deactivate", function (e) {
            e.stopPropagation();
            var userId = $(this).attr("data-user-id");
            var loader = $("#data-delete-loader-" + userId);
            loader.show();
            $("#btnDeleted" + userId).hide();
            $(this).closest(".popover").popover("hide");
            setTimeout(function () {
              self.deactivateUser(userId, !self.showDeletedUsers, function () {
                loader.hide();
                $("#btnDeleted" + userId).show();
              });
            }, 150);
          });
        $("#adminTable .reactivate-icon")
          .off("click")
          .on("click", function (e) {
            e.stopPropagation();
            self.reactivateUser($(this).attr("data-user-id"));
          });

        $(document)
          .undelegate(".popover-btn-cancel", "click")
          .on("click", ".popover-btn-cancel", function (e) {
            e.stopPropagation();
            $(this).closest(".popover").popover("hide");
          });
        $(document).on("click", function () {
          $("#adminTable .popover").popover("hide");
        });
      },
      addFilterPlaceHolders: function () {
        $("#adminTable .filterControl input").attr(
          "placeholder",
          i18next.t("Enter Text")
        );
        $("#adminTable .filterControl select option[value='']").text(
          i18next.t("Select")
        );
      },
      isPatientsList: function () {
        return $("#adminTableContainer").hasClass("patient-view"); //check if this is a patients list
      },
      /*
       * a function dedicated to hide account creation button based on org name from setting
       * @params
       * setting_name String, generally a configuration/setting variable name whose values corresponds to an org name of interest e.g. PROTECTED_ORG
       * params Object, passed to ajax call to get configuration settings
       */
      setCreateAccountVisByTopOrgSetting: function (setting_name, params) {
        if (!setting_name) {
          return false;
        }
        var self = this,
          tnthAjax = this.getDependency("tnthAjax");
        params = params || {};
        tnthAjax.sendRequest(
          "/api/settings",
          "GET",
          this.userId,
          params,
          function (data) {
            if (!data || data.error || !data[setting_name]) {
              return false;
            }
            var nonMatch = $.grep(self.topLevelOrgs, function (org) {
              return data[setting_name] !== org;
            });
            //has top org affiliation other than matched org setting
            if (nonMatch.length) {
              return false;
            }
            //has top org affiliation with matched org setting
            var match = $.grep(self.topLevelOrgs, function (org) {
              return data[setting_name] === org;
            });
            if (match.length === 0) {
              return false;
            }
            self.setCreateAccountVis(true);
          }
        );
      },
      /*
       * a function specifically created to handle MedidataRave-related UI events/changes
       */
      handleMedidataRave: function (params) {
        if (!this.isPatientsList()) {
          //check if this is a patients list
          return false;
        }
        //hide account creation button based on PROTECTED_ORG setting
        this.setCreateAccountVisByTopOrgSetting("PROTECTED_ORG", params);
      },
      /*
       * a function dedicated to handle MUSIC-related UI events/changes
       */
      handleMusic: function (params) {
        if (!this.isPatientsList()) {
          //check if this is a patients list
          return false;
        }
        //hide account creation button based on ACCEPT TERMS ON NEXT ORG setting (MUSIC)
        this.setCreateAccountVisByTopOrgSetting(
          "ACCEPT_TERMS_ON_NEXT_ORG",
          params
        );
      },
      setCreateAccountVis: function (hide) {
        var createAccountElements = $(
          "#patientListOptions .or, #createUserLink"
        );
        if (hide) {
          createAccountElements.css("display", "none");
          return;
        }
        createAccountElements.css("display", "block");
      },
      handleDisableFields: function () {
        if (this.isAdminUser()) {
          return false;
        }
        this.handleMedidataRave();
        this.handleMusic();
        //can do other things related to disabling fields here if need be
      },
      hasOrgsSelector: function () {
        return $("#orglistSelector").length;
      },
      siteFilterApplied: function () {
        return (
          this.currentTablePreference &&
          this.currentTablePreference.filters &&
          this.currentTablePreference.filters.orgs_filter_control &&
          typeof this.currentTablePreference.filters.orgs_filter_control ===
            "object" &&
          this.currentTablePreference.filters.orgs_filter_control.length
        );
      },
      initOrgsFilter: function () {
        var orgFields = $("#userOrgs input[name='organization']");
        var fi = this.currentTablePreference
          ? this.currentTablePreference.filters
          : {};
        var fa = this.siteFilterApplied() ? fi.orgs_filter_control : [];
        orgFields.each(function () {
          $(this).prop("checked", false);
          var oself = $(this),
            val = oself.val();
          fa = fa.map(function (item) {
            return String(item);
          });
          oself.prop("checked", fa.indexOf(String(val)) !== -1);
        });
        if (this.getHereBelowOrgs().length === 1) {
          orgFields.prop("checked", true);
        }
      },
      initSubStudyOrgsVis: function () {
        var orgFields = $("#userOrgs input[name='organization']");
        let ot = this.getOrgTool();
        let isSubStudyPatientView = this.isSubStudyPatientView();
        orgFields.each(function () {
          var val = $(this).val();
          if (
            val &&
            isSubStudyPatientView &&
            !ot.isSubStudyOrg(val, { async: true })
          ) {
            $(this).attr("disabled", true);
            $(this).parent("label").addClass("disabled");
          }
        });
      },
      setOrgsFilterWarning: function () {
        if (!this.siteFilterApplied()) {
          return;
        }
        /*
         * display organization filtered popover warning text
         */
        $("#adminTableToolbar .orgs-filter-warning").popover("show");
        setTimeout(function () {
          $("#adminTableToolbar .orgs-filter-warning").popover("hide");
        }, 10000);
      },
      initOrgsEvent: function () {
        var ofields = $("#userOrgs input[name='organization']");
        if (ofields.length === 0) {
          return false;
        }
        var self = this;

        $("#orglistSelector .orgs-filter-warning").popover();

        $("body").on("click", function (e) {
          if ($(e.target).closest("#orglistSelector").length === 0) {
            $("#orglistSelector").removeClass("open");
          }
        });

        $("#orglist-dropdown").on("click touchstart", function () {
          $(this)
            .find(".glyphicon-menu-up, .glyphicon-menu-down")
            .toggleClass("tnth-hide"); //toggle menu up/down button
          self.initSubStudyOrgsVis();
          setTimeout(function () {
            self.setOrgsMenuHeight(95);
            self.clearFilterButtons();
          }, 100);
        });
        /* attach orgs related events to UI components */
        ofields.each(function () {
          $(this).on("click touchstart", function (e) {
            e.stopPropagation();
            var isChecked = $(this).is(":checked");
            var childOrgs = self.getSelectedOrgHereBelowOrgs($(this).val());
            if (childOrgs && childOrgs.length) {
              childOrgs.forEach(function (org) {
                $(
                  "#userOrgs input[name='organization'][value='" + org + "']"
                ).prop("checked", isChecked);
              });
            }
            if (!isChecked) {
              var ot = self.getOrgTool();
              var currentOrgId = $(this).val();
              var parentOrgId = ot.getParentOrgId($(this).val());
              if (parentOrgId) {
                /*
                 * if all child organizations(s) are unchecked under a parent org, uncheck that parent org as well
                 */
                var cn = ot.getHereBelowOrgs([parentOrgId]);
                var hasCheckedChilds = cn.filter(function (item) {
                  return (
                    parseInt(item) !== parseInt(currentOrgId) &&
                    parseInt(item) !== parseInt(parentOrgId) &&
                    ot.getElementByOrgId(item).prop("checked")
                  );
                });
                if (!hasCheckedChilds.length) {
                  ot.getElementByOrgId(parentOrgId).prop("checked", false);
                }
              }
            }
            self.setOrgsSelector({
              selectAll: false,
              clearAll: false,
              close: false,
            });
            self.onOrgListSelectFilter();
          });
        });
        $("#orglist-selectall-ckbox").on("click touchstart", function (e) {
          e.stopPropagation();
          var orgsList = [];
          self.setOrgsSelector({
            selectAll: true,
            clearAll: false,
            close: false,
          });
          $("#userOrgs input[name='organization']")
            .filter(":visible")
            .each(function () {
              if ($(this).css("display") !== "none") {
                $(this).prop("checked", true);
                orgsList.push($(this).val());
              }
            });
          if (orgsList.length === 0) return;
          self.onOrgListSelectFilter();
        });
        $("#orglist-clearall-ckbox").on("click touchstart", function (e) {
          e.stopPropagation();
          self.clearOrgsSelection();
          self.setOrgsSelector({
            selectAll: false,
            clearAll: true,
            close: false,
          });
          self.onOrgListSelectFilter();
        });
        $("#orglist-close-ckbox").on("click touchstart", function (e) {
          e.stopPropagation();
          self.setOrgsSelector({
            selectAll: false,
            clearAll: false,
            close: true,
          });
          $("#orglistSelector").trigger("click");
          return false;
        });
      },
      clearOrgsSelection: function () {
        $("#userOrgs input[name='organization']").prop("checked", false);
        this.clearFilterButtons();
      },
      onOrgListSelectFilter: function () {
        this.setTablePreference(
          this.userId,
          this.tableIdentifier,
          null,
          null,
          null,
          function () {
            // callback from setting the filter preference
            // this ensures that the table filter preference is saved before reloading the page
            // so the backend can present patient list based on that saved preference
            setTimeout(
              function () {
                // this.showLoader();
                // location.reload();
                $("#adminTable").bootstrapTable("refresh");
              }.bind(this),
              350
            );
          }.bind(this)
        );
      },
      getDefaultTablePreference: function () {
        return {
          sort_field: this.ROW_ID,
          sort_order: "desc",
        };
      },
      getTablePreference: function (
        userId,
        tableName,
        setFilter,
        setColumnSelections
      ) {
        if (this.currentTablePreference) {
          return this.currentTablePreference;
        }
        var prefData = null,
          self = this,
          uid = userId || self.userId;
        var tableIdentifier = tableName || self.tableIdentifier;
        var tnthAjax = self.getDependency("tnthAjax");

        tnthAjax.getTablePreference(
          uid,
          tableIdentifier,
          {
            sync: true,
          },
          function (data) {
            if (!data || data.error) {
              return false;
            }
            prefData = data || self.getDefaultTablePreference();
            self.currentTablePreference = prefData;

            if (setFilter) {
              //set filter values
              self.setTableFilters(uid);
            }
            if (setColumnSelections) {
              //set column selection(s)
              self.setColumnSelections();
            }
          }
        );
        return prefData;
      },
      setColumnSelections: function () {
        if (!this.sortFilterEnabled) {
          return false;
        }
        var prefData = this.getTablePreference(
          this.userId,
          this.tableIdentifier
        );
        var hasColumnSelections =
          prefData && prefData.filters && prefData.filters.column_selections;
        if (!hasColumnSelections) {
          return false;
        }
        var visibleColumns =
          $("#adminTable").bootstrapTable("getVisibleColumns");
        visibleColumns.forEach(function (c) {
          //hide visible columns
          if (String(c.class).toLowerCase() === "always-visible") {
            return true;
          }
          $("#adminTable").bootstrapTable("hideColumn", c.field);
        });
        prefData.filters.column_selections.forEach(function (column) {
          //show column(s) based on preference
          $(
            ".fixed-table-toolbar input[type='checkbox'][data-field='" +
              column +
              "']"
          ).prop("checked", true);
          $("#adminTable").bootstrapTable("showColumn", column);
        });
      },
      setTableFilters: function (userId) {
        var prefData = this.currentTablePreference,
          tnthAjax = this.getDependency("tnthAjax");
        if (!prefData) {
          tnthAjax.getTablePreference(
            userId || this.userId,
            this.tableIdentifier,
            {
              sync: true,
            },
            function (data) {
              if (!data || data.error) {
                return false;
              }
              prefData = data;
            }
          );
        }
        if (prefData && prefData.filters) {
          //set filter values
          var fname = "";
          for (var item in prefData.filters) {
            fname = "#adminTable .bootstrap-table-filter-control-" + item;
            if ($(fname).length === 0) {
              continue;
            }
            //note this is based on the trigger event for filtering specify in the plugin
            $(fname).val(prefData.filters[item]);
            if (prefData.filters[item]) {
              $(fname).addClass("active");
            }
            // if ($(fname).get(0))
            //   $(fname).trigger(
            //     $(fname).get(0).tagName === "INPUT" ? "keyup" : "change"
            //   );
          }
        }
      },
      setTablePreference: function (
        userId,
        tableName,
        sortField,
        sortOrder,
        filters,
        callback
      ) {
        var tnthAjax = this.getDependency("tnthAjax");
        tableName = tableName || this.tableIdentifier;
        if (!tableName) {
          return false;
        }
        userId = userId || this.userId;
        var data = this.getDefaultTablePreference();
        if (sortField && sortOrder) {
          data["sort_field"] = sortField;
          data["sort_order"] = sortOrder;
        } else {
          //get selected sorted field information on UI
          var sortedField = $("#adminTable th[data-field]").has(
            ".sortable.desc, .sortable.asc"
          );
          if (sortedField.length > 0) {
            data["sort_field"] = sortedField.attr("data-field");
            var sortedOrder = "desc";
            sortedField.find(".sortable").each(function () {
              if ($(this).hasClass("desc")) {
                sortedOrder = "desc";
              } else if ($(this).hasClass("asc")) {
                sortedOrder = "asc";
              }
            });
            data["sort_order"] = sortedOrder;
          }
        }
        var __filters = filters || {};

        //get fields
        if (Object.keys(__filters).length === 0) {
          $(
            "#adminTable .filterControl select, #adminTable .filterControl input"
          ).each(function () {
            if ($(this).val()) {
              var field = $(this).closest("th").attr("data-field");
              if ($(this).get(0)) {
                __filters[field] =
                  $(this).get(0).nodeName.toLowerCase() === "select"
                    ? $(this).find("option:selected").text()
                    : $(this).val();
              }
            }
          });
        }
        //get selected orgs from the filter list by site control
        var selectedOrgs = [];
        $("#userOrgs input[name='organization']").each(function () {
          if ($(this).is(":checked") && $(this).css("display") !== "none") {
            selectedOrgs.push(parseInt($(this).val()));
          }
        });
        __filters["orgs_filter_control"] = selectedOrgs;
        //get column selections
        __filters["column_selections"] = [];
        $(
          ".fixed-table-toolbar input[type='checkbox'][data-field]:checked"
        ).each(function () {
          __filters["column_selections"].push($(this).attr("data-field"));
        });
        data["filters"] = __filters;

        if (Object.keys(data).length > 0) {
          // make this a synchronous call
          tnthAjax.setTablePreference(
            userId,
            this.tableIdentifier,
            {
              data: JSON.stringify(data),
              sync: true,
            },
            callback
          );
          this.currentTablePreference = data;
        }
      },
      getReportModal: function (patientId, options) {
        $("#patientReportModal").modal("show");
        this.patientReports.loading = true;
        var self = this,
          tnthDates = self.getDependency("tnthDates"),
          tnthAjax = self.getDependency("tnthAjax");
        options = options || {};
        tnthAjax.patientReport(patientId, options, function (data) {
          self.patientReports.data = [];
          if (!data || data.error) {
            self.patientReports.message = i18next.t(
              "Error occurred retrieving patient report"
            );
            return false;
          }
          if (data["user_documents"] && data["user_documents"].length > 0) {
            var existingItems = {},
              count = 0;
            var documents = data["user_documents"].sort(function (a, b) {
              //sort to get the latest first
              return new Date(b.uploaded_at) - new Date(a.uploaded_at);
            });
            documents.forEach(function (item) {
              var c = item["contributor"];
              if (c && !existingItems[c]) {
                //only draw the most recent, same report won't be displayed
                if (
                  options.documentDataType &&
                  String(options.documentDataType).toLowerCase() !==
                    String(c).toLowerCase()
                ) {
                  return false;
                }
                self.patientReports.data.push({
                  contributor: item.contributor,
                  fileName: item.filename,
                  date: tnthDates.formatDateString(item.uploaded_at, "iso"),
                  download:
                    "<a title='" +
                    i18next.t("Download") +
                    "' href='" +
                    "/api/user/" +
                    item["user_id"] +
                    "/user_documents/" +
                    item["id"] +
                    "'><i class='fa fa-download'></i></a>",
                });
                existingItems[c] = true;
                count++;
              }
            });
            if (count > 1) {
              $("#patientReportModal .modal-title").text(
                i18next.t("Patient Reports")
              );
            } else {
              $("#patientReportModal .modal-title").text(
                i18next.t("Patient Report")
              );
            }
            self.patientReports.message = "";
            $("#patientReportContent .btn-all").attr(
              "href",
              "patient_profile/" + patientId + "#profilePatientReportTable"
            );
          } else {
            self.patientReports.message = i18next.t("No report data found.");
          }
          setTimeout(function () {
            self.patientReports.loading = false;
          }, 550);
        });
      },
      rowLinkEvent: function () {
        $("#admin-table-body.data-link").delegate("tr", "click", function (e) {
          if (e.target && e.target.tagName.toLowerCase() !== "td") {
            if (e.target.tagName.toLowerCase() === "a" && e.target.click) {
              return;
            }
          }
          e.preventDefault();
          e.stopPropagation();
          var row = $(this).closest("tr");
          if (row.hasClass("deleted-user-row") || row.hasClass("loading")) {
            return false;
          }
          if (!row.hasClass("no-records-found")) {
            $("#adminTable .popover").popover("hide");
            document.location = $(this).closest("tr").attr("data-link");
          }
        });
      },
      deactivationEnabled: function () {
        return $("#chkDeletedUsersFilter").length > 0;
      },
      reactivateUser: function (userId) {
        var tnthAjax = this.getDependency("tnthAjax"),
          self = this;
        if (!this.isDeactivatedRow(userId)) {
          return false;
        }
        $("#" + self.ROW_ID_PREFIX + userId).addClass("loading");
        tnthAjax.reactivateUser(
          userId,
          {
            async: true,
          },
          function (data) {
            $("#" + self.ROW_ID_PREFIX + userId).removeClass("loading");
            if (data.error) {
              alert(data.error);
              return;
            }
            self.handleReactivatedRow(userId);
            setTimeout(function () {
              self.handleDeletedUsersVis(); //reset rows displayed
            }, 150);
          }
        );
      },
      deactivateUser: function (userId, hideRow, callback) {
        callback = callback || function () {};
        if (!userId) {
          callback({
            error: i18next.t("User id is required."),
          });
          return false;
        }
        if (this.isDeactivatedRow(userId)) {
          callback();
          return false;
        }
        var tnthAjax = this.getDependency("tnthAjax"),
          self = this;
        $("#" + self.ROW_ID_PREFIX + userId).addClass("loading");
        tnthAjax.deactivateUser(
          userId,
          {
            async: true,
          },
          function (data) {
            $("#" + self.ROW_ID_PREFIX + userId).removeClass("loading");
            if (data.error) {
              callback({
                error: data.error,
              });
              alert(data.error);
              return;
            }
            callback();
            if (hideRow) {
              $("#" + self.ROW_ID_PREFIX + userId).fadeOut();
            }
            self.handleDeactivatedRow(userId);
            setTimeout(function () {
              self.handleDeletedUsersVis(); //reset rows displayed
            }, 150);
          }
        );
      },
      getRowData: function (userId) {
        if (!userId) {
          return false;
        }
        return $("#adminTable").bootstrapTable("getRowByUniqueId", userId);
      },
      isDeactivatedRow: function (userId) {
        var rowData = this.getRowData(userId);
        return (
          rowData &&
          String(rowData.activationstatus).toLowerCase() === "deactivated"
        );
      },
      resetRowVisByActivationStatus: function () {
        var self = this;
        $("#adminTable [data-index]").each(function () {
          var userId = $(this).attr("data-uniqueid");
          if (self.isDeactivatedRow(userId)) {
            self.handleDeactivatedRowVis(userId);
          } else {
            self.handleReactivatedRowVis(userId);
          }
        });
      },
      updateFieldData: function (userId, data) {
        if (!userId || !data) {
          return false;
        }
        $("#adminTable").bootstrapTable("updateCell", data);
      },
      getRowIndex: function (userId) {
        if (!userId) {
          return false;
        }
        return $("#" + this.ROW_ID_PREFIX + userId).attr("data-index");
      },
      handleDeactivatedRow: function (userId) {
        this.updateFieldData(userId, {
          index: this.getRowIndex(userId),
          field: "activationstatus",
          value: "deactivated",
          reinit: true,
        });
        this.handleDeactivatedRowVis(userId);
      },
      handleDeactivatedRowVis: function (userId) {
        if (!userId) {
          return false;
        }
        var allowReactivate = $("#adminTable").attr("data-allow-reactivate");
        $("#" + this.ROW_ID_PREFIX + userId)
          .addClass("deleted-user-row")
          .addClass("rowlink-skip")
          .find(".deleted-button-cell")
          .html(
            '<span class="text-display">{inactivetext}</span><i data-user-id="{userid}" aria-hidden="true" title="Reactivate account" class="fa fa-undo reactivate-icon {class}"></i>'
              .replace("{class}", allowReactivate ? "" : "tnth-hide")
              .replace("{userid}", userId)
              .replace("{inactivetext}", i18next.t("Inactive"))
          )
          .find("a.profile-link")
          .remove();
        if (!this.showDeletedUsers) {
          $("#" + this.ROW_ID_PREFIX + userId).hide();
        }
      },
      handleReactivatedRow: function (userId) {
        if (!userId) {
          return false;
        }
        this.updateFieldData(userId, {
          index: this.getRowIndex(userId),
          field: "activationstatus",
          value: "activated",
          reinit: true,
        });
        this.handleReactivatedRowVis(userId);
      },
      handleReactivatedRowVis: function (userId) {
        if (!userId) {
          return false;
        }
        $("#data_row_" + userId)
          .removeClass("deleted-user-row")
          .removeClass("rowlink-skip")
          .find(".deleted-button-cell")
          .html(
            '<button id="btnDeleted{userid}" data-user-id="{userid}" type="button" class="btn btn-default btn-delete-user" data-original-title="" title=""><em>{buttontext}</em></button>'
              .replace(/\{userid\}/g, userId)
              .replace("{buttontext}", i18next.t("Deactivate"))
          )
          .append("<a class='profile-link'></a>");
        if (this.showDeletedUsers) {
          $("#" + this.ROW_ID_PREFIX + userId).hide();
        }
      },
    },
  }));
})();
