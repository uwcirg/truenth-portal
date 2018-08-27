(function() {
    /*global getUrlParameter*/
    var typeInTous = function(data, type, status) {
        var found = false, isActive = String(status) === "active";
        (data.tous).forEach(function(item) {
            if (!found &&
                $.trim(item.type) === $.trim(type) &&
                String($.trim(item.active)) === String(isActive)) {
                found = true;
            }
        });
        return found;
    };
    var updateTerms = function(data) {
        if (data.tous) {
            $("#termsCheckbox label.terms-label").each(function() {
                var itemFound = 0, self = $(this);
                self.find("[data-type='terms']").each(function() {
                    var type = $(this).attr("data-tou-type");
                    if (typeInTous(data, type, "active")) {
                        itemFound+=1;
                        $("#termsCheckbox [data-tou-type='" + type + "']").attr("data-agree", "true"); //set the data-agree attribute for the corresponding consent item
                    }
                });
                if (itemFound > 0) {
                    if (self.find("[data-agree='false']").length === 0) { // make sure that all items are agreed upon before checking the box
                        self.find("i").removeClass("fa-square-o").addClass("fa-check-square-o").addClass("edit-view");
                        var vs = self.find(".display-view");
                        if (vs.length > 0) {
                            self.show();
                            vs.show();
                            self.find(".edit-view").each(function() {
                                $(this).hide();
                            });
                        }
                    }
                    self.show().removeClass("tnth-hide");
                }
            });
        }
    };
    var patientId = getUrlParameter("subject_id");
    var entryMethod = getUrlParameter("entry_method");
    var urlRedirect = getUrlParameter("redirect_url");
    var topOrgName = $("#wcsTopOrganization").attr("data-name");
    var topOrgId = $("#wcsTopOrganization").attr("data-id");
    var tVar = setInterval(function() {
        if ($("#tnthNavWrapper").length > 0) {
            $("#tnthNavWrapper, #homeFooter, .watermark").each(function() {
                $(this).addClass("hidden-print");
            });
            clearInterval(tVar);
        }
    }, 1000);
    var tnthAjax = window.portalModules.tnthAjax;

    $(document).ready(function() {
        //get still needed
        tnthAjax.getStillNeededCoreData(patientId, true, null, entryMethod);
        //populate existing checkbox(es)
        tnthAjax.getTerms(patientId, false, true, function(data) {
            updateTerms(data);
            if ($("[data-agree='false']").length === 0) {
                $(".continue-msg-wrapper").show();
            }
        });
        $(".intro-text").text($(".intro-text").text().replace("[organization]", topOrgName));

        if ($(".terms-tick-box-text[data-org='" + topOrgName + "']").length > 0) {
            $(".terms-tick-box-text[data-org]").each(function() {
                if (String($(this).attr("data-org")).toLowerCase() === String(topOrgName).toLowerCase()) {
                    $(this).show();
                } else {
                    $(this).hide();
                }
            });
        } else {
            $($(".terms-tick-box-text[data-org]").get(0)).show();
        }
        $(".terms-tick-box").each(function() {
            $(this).on("click", function() {
                var container = $(this).closest(".terms-text-container");
                var termsItems = container.find("[data-type='terms']");
                var tickBox = $(this);
                termsItems.each(function() {
                    if (String($(this).attr("data-agree")) === "false") {
                        var type = $(this).attr("data-tou-type");
                        if (type) {
                            var theTerms = {};
                            theTerms["agreement_url"] = $(this).attr("data-url");
                            theTerms["type"] = type;
                            if (topOrgId) {
                                theTerms["organization_id"] = topOrgId;
                            }
                            $("#termsCheckbox .data-saving-indicator").removeClass("tnth-hide");
                            tnthAjax.postTermsByUser(patientId, theTerms, function(data) {
                                if (!data.error && $("[data-agree='false']").length === 0) {
                                    $(".continue-msg-wrapper").fadeIn();
                                }
                                $("#termsCheckbox .data-saving-indicator").addClass("tnth-hide");
                            });
                        }
                        tickBox.removeClass("fa-square-o").addClass("fa-check-square-o"); // Update UI
                        $(this).attr("data-agree", "true");
                    }
                });
               
            });
        });
        $(".button-container").each(function() {
            $(this).prepend("<div class='loading-message-indicator'><i class='fa fa-spinner fa-spin fa-2x'></i></div>");
        });
        $("#continue").on("click", function() {
            $(this).hide();
            $(".loading-message-indicator").show();
            setTimeout(function() {
                window.location = urlRedirect;
            }, 100);
        });
        $(".consent-form-checkbox").each(function() {
            $(this).on("click", function() {
                $(this).toggleClass("fa-square-o fa-check-square-o");
            });
        });
        $("#consentPrintButton").on("click", function() {
            var elem = document.getElementById("websiteDeclarationForm");
            $(elem).removeClass("hidden-print");
            var domClone = elem.cloneNode(true);
            var $printSection = document.getElementById("printSection");
            if (!$printSection) {
                $printSection = document.createElement("div");
                $printSection.id = "printSection";
                document.body.appendChild($printSection);
            }
            $printSection.innerHTML = "";
            $printSection.appendChild(domClone);
            $(elem).addClass("hidden-print");
            window.print();
        });
        $("#websiteDeclarationFormModal").on("hide.bs.modal", function() {
            $(this).removeClass("fade");
        });
    });
})();

