/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/

function equalHeightBoxes(passClass) {
    var windowsize = $(window).width();
    // Switch back to auto for small screen or to recalculate on larger
    $('.'+passClass).css("height","auto");
    if (windowsize > 768 && $('.'+passClass).length > 1) {
        var elementHeights = $('.'+passClass).map(function() {
            return $(this).height();
        }).get();
        // Math.max takes a variable number of arguments
        // `apply` is equivalent to passing each height as an argument
        var maxHeight = Math.max.apply(null, elementHeights);
        // Set each height to the max height
        $('.'+passClass).height(maxHeight);
    }
}

// Return an XHR without XHR header so  it doesn't need to be explicitly allowed with CORS
function xhr_function(){
    // Get new xhr object using default factory
    var xhr = jQuery.ajaxSettings.xhr();
    // Copy the browser's native setRequestHeader method
    var setRequestHeader = xhr.setRequestHeader;
    // Replace with a wrapper
    xhr.setRequestHeader = function(name, value) {
        // Ignore the X-Requested-With header
        if (name == 'X-Requested-With') return;
        // Otherwise call the native setRequestHeader method
        // Note: setRequestHeader requires its 'this' to be the xhr object,
        // which is what 'this' is here when executed.
        setRequestHeader.call(this, name, value);
    }
    // pass it on to jQuery
    return xhr;
}
// AJAX callback
function embed_page(data){
    $("#mainNav")
        // Embed data returned by AJAX call into container element
        .html(data);
    // Wait until TrueNTH logo loads before displaying the navWrapper. Avoid having content flash when CSS hasn't loaded
    $("img.tnth-topnav-wordmark").load(function(){
        $("#tnthNavWrapper").show();
    });
    // Todo: add "data-*" HTML attribute
}

// Loading indicator that appears in UI on page loads and when saving
var loader = function(show) {
    if (show) {
        $("#profileForm").addClass("loading");
        $("#loadingIndicator").show();
    } else {
        // Otherwise we'll hide it
        $("#loadingIndicator").fadeOut();
        $("#profileForm").removeClass("loading");
    }
}

var fillContent = {
    "clinical": function(data) {
        $.each(data.entry, function(i,val){
            var clinicalItem = val.content.code.coding[0].display;
            if (clinicalItem == "PCa diagnosis") {
                clinicalItem = "pca_diag";
            } else if (clinicalItem == "treatment begun") {
                clinicalItem = "tx";
            } else if (clinicalItem == "PCa metastasize diagnosis") {
                clinicalItem = "pca_metastasize";
            }
            $('div[data-topic='+clinicalItem+']').fadeIn();
            var clinicalValue = val.content.valueQuantity.value;
            var $radios = $('input:radio[name='+clinicalItem+']');
            if($radios.is(':checked') === false) {
                $radios.filter('[value='+clinicalValue+']').prop('checked', true);
            }
            // Display clinics if any value is false or if all are answered
            if (clinicalValue == "false" || i == 3) {
                $("#clinics").fadeIn();
            }
        })
    },
    "demo": function(data) {
        $('#firstname').val(data.name.given);
        $('#lastname').val(data.name.family);
        if (data.birthDate) {
            var bdArray = data.birthDate.split("-");
            $("#year").val(bdArray[0]);
            $("#month").val(bdArray[1]);
            $("#date").val(bdArray[2]);
        }
        // TODO - add email and phone for profile page use
        // Only on profile page
        $.each(data.extension[0].valueCodeableConcept.coding,function(i,val){
            $("#userEthnicity input:radio[value="+val.code+"]").prop('checked', true);
            // Way to handle non-standard codes - output but hide, for submitting on update
            if ($("#userEthnicity input:radio[value="+val.code+"]").length == 0) {
                $("#userEthnicity").append("<input class='tnth-hide' type='checkbox' checked name='ethnicity' value='"+val.code+"' data-label='"+val.display+"' />");
            }
        });
        // Get Races
        $.each(data.extension[1].valueCodeableConcept.coding,function(i,val){
            $("#userRace input:checkbox[value="+val.code+"]").prop('checked', true);
            // Way to handle non-standard codes
            if ($("#userRace input:checkbox[value="+val.code+"]").length == 0) {
                // If there is any non-standard, then check the "other" in the UI
                $("#userRace input:checkbox[value=2131-1]").prop('checked', true);
                // Add hidden list of non-standard for form submission
                $("#userRace").append("<input class='tnth-hide' type='checkbox' checked name='race' value='"+val.code+"' data-label='"+val.display+"' />");
                //$("#raceOtherVal").fadeToggle();
            }
        });
    },
    "orgs": function(data) {
        $.each(data.careProvider,function(i,val){
            var orgID = val.reference.split("/").pop();
            $("body").find("#userOrgs input.clinic:checkbox[value="+orgID+"]").prop('checked', true);
        });
    },
    "roles": function(data,isProfile) {
        $.each(data.roles, function(i,val){
            var userRole = val.name;
            // Handle profile differently than initial_queries
            if (isProfile) {
                $.each(data.roles,function(i,val){
                    $("#userRoles input:checkbox[value="+val.name+"]").prop('checked', true);
                });
            } else {
                var $radios = $('input[name=user_type]');
                if($radios.is(':checked') === false) {
                    $radios.filter('[value='+userRole+']').prop('checked', true);
                }
                if (userRole == "patient") {
                    $("#patientQ, #bdGroup").fadeIn();
                    $("#clinics").hide();
                    return false;
                } else if (userRole == "partner") {
                    $("#clinics").fadeIn();
                    $("#patientQ, #bdGroup").hide();
                }
            }
        })
    }
};

var assembleContent = {
    "demo": function(userId,onProfile) {
        var m = parseInt($("#month").val());
        var d = parseInt($("#date").val());
        var y = parseInt($("#year").val());
        // If all three have been entered, run check
        var goodDate = false;
        if (m && d && y) {
            var today = new Date();
            // Check to see if this is a real date
            var date = new Date(y,m-1,d);
            if (date.getFullYear() == y && date.getMonth() + 1 == m && date.getDate() == d) {
                goodDate = true;
                // Only allow if birthdate is before today
                if (date.setHours(0,0,0,0) >= today.setHours(0,0,0,0)) {
                    goodDate = false;
                    errorMsg = "Your birthdate must be in the past.";
                }
            }
        }
        if (y.toString().length < 3) {
            goodDate = false;
        }
        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["name"] = {
            "given": $("input[name=firstname]").val(),
            "family": $("input[name=lastname]").val()
        };
        // After tests display errors if necessary
        if (goodDate) {
            $("#birthday").val(y+"-"+m+"-"+d);
            demoArray["birthDate"] = $("input[name=birthDate]").val();
        }
        if (onProfile) {
            $.each($("#userOrgs input:checkbox:checked"),function(i,v){
                if ($(this).attr("data-parent-id")) {
                    $("#userOrgs input:checkbox[value="+$(this).attr("data-parent-id")+"]").prop('checked', true);
                }
            });
            var orgIDs = $("#userOrgs input:checkbox:checked").map(function(){
                return { reference: "api/organization/"+$(this).val() };
            }).get();
            var parentId;
            $.each($("#userOrgs input:checkbox:checked"),function(i,v){
                if ($(this).attr("data-parent-id") && $(this).attr("data-parent-id") != parentId) {
                    orgIDs.push({reference: "api/organization/"+$(this).attr("data-parent-id")});
                    parentId = $(this).attr("data-parent-id");
                }
            });
            demoArray["careProvider"] = orgIDs;

            // Grab profile field values - looks for regular and hidden, can be checkbox or radio
            var ethnicityIDs = $("#userEthnicity input:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
            }).get();
            // Look for race checkboxes, can be hidden
            var raceIDs = $("#userRace input:checkbox:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
            }).get();
            demoArray["gender"] = $("input[name=sex]:checked").val();
            demoArray["telecom"] = [
                { "system": "email", "value": $("input[name=email]").val() },
                { "system": "phone", "value": $("input[name=phone]").val() }
            ];
            demoArray["extension"] = [
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
                    "valueCodeableConcept": {
                        "coding": ethnicityIDs
                    }
                },
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-race",
                    "valueCodeableConcept": {
                        "coding": raceIDs
                    }
                }
            ];
        }
        tnthAjax.putDemo(userId,demoArray);
    },
    "orgs": function(userId) {
        $.each($("#userOrgs input:checkbox:checked"),function(i,v){
            if ($(this).attr("data-parent-id")) {
                $("#userOrgs input:checkbox[value="+$(this).attr("data-parent-id")+"]").prop('checked', true);
            }
        });

        var orgIDs = $("#userOrgs input:checkbox:checked").map(function(){
            return { reference: "api/organization/"+$(this).val() };
        }).get();

        var parentId;
        $.each($("#userOrgs input:checkbox:checked"),function(i,v){
            if ($(this).attr("data-parent-id") && $(this).attr("data-parent-id") != parentId) {
                orgIDs.push({reference: "api/organization/"+$(this).attr("data-parent-id")});
                parentId = $(this).attr("data-parent-id");
            }
        });
        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["careProvider"] = orgIDs;
        tnthAjax.putDemo(userId, demoArray);
    }
}

var tnthAjax = {
    "getOrgs": function(userId) {
        loader(true);
        $.ajax ({
            type: "GET",
            url: '/api/organization'
        }).done(function(data) {
            $.each(data.entry,function(i,val){
                if (val.partOf) {
                    var getParent = val.partOf.reference.split("/").pop();
                    var clinic = '<div class="checkbox"><label>' +
                        '<input class="clinic" type="checkbox" name="organization" value="'+
                        val.id +'" data-parent-id="'+getParent+'" />'+
                        val.name +
                        '</label></div>';
                    $("#clinics"+getParent).append(clinic);
                }
            });
            tnthAjax.getDemo(userId);
        }).fail(function() {
            console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "getDemo": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
        }).done(function(data) {
            fillContent.orgs(data);
            fillContent.demo(data);
            loader();
        }).fail(function() {
            console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "putDemo": function(userId,toSend) {
        $.ajax ({
            type: "PUT",
            url: '/api/demographics/'+userId,
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {
        }).fail(function() {
            console.log("Problem updating role on server.");
        });
    },
    "getRoles": function(userId,isProfile) {
        $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+'/roles'
        }).done(function(data) {
            fillContent.roles(data,isProfile);
        }).fail(function() {
            console.log("Problem retrieving data from server.");

        });
    },
    "putRoles": function(userId,toSend) {
        $.ajax ({
            type: "PUT",
            url: '/api/user/'+userId+'/roles',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {

        }).fail(function() {
            console.log("Problem updating role on server.");

        });
    },
    "deleteRoles": function(userId,toSend) {
        console.log('deleting')
        $.ajax ({
            type: "DELETE",
            url: '/api/user/'+userId+'/roles',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {

        }).fail(function() {
            console.log("Problem updating role on server.");

        });
    },
    "getClinical": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/clinical'
        }).done(function(data) {
            fillContent.clinical(data);
        }).fail(function() {
            console.log("Problem retrieving data from server.");
        });
    },
    "putClinical": function(userId, toCall, toSend) {
        $.ajax ({
            type: "POST",
            url: '/api/patient/'+userId+'/clinical/'+toCall,
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify({value: toSend})
        }).done(function() {

        }).fail(function() {
            alert("There was a problem saving your answers. Please try again.");
        });
    }
};

$(document).ready(function() {
    var initial_xhr = $.ajax({
        url: PORTAL_NAV_PAGE,
        type:'GET',
        contentType:'text/plain',
        //dataFilter:data_filter,
        //xhr: xhr_function,
        crossDomain: true
        //xhrFields: {withCredentials: true},
    }, 'html')
    .done(function(data) {
        embed_page(data);
        //showSearch();
    })
    .fail(function(jqXHR, textStatus, errorThrown) {
        alert("Error loading nav elements from " + PORTAL_HOSTNAME);
    })
    .always(function() {
        // alert( "complete" );
    });

    // Reveal footer after load to avoid any flashes will above content loads
    $("#homeFooter").show();

});