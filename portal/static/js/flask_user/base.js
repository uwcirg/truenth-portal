$(document).on("ready", function() {
    $("input[type='text']").on("blur paste", function() {
        $(this).val($.trim($(this).val()));
    });
    var SUBMIT_CLASS_CONTAINER_NAME = ".form___submit_container";
    if ($(SUBMIT_CLASS_CONTAINER_NAME).length) {
        $(SUBMIT_CLASS_CONTAINER_NAME)
        .css("width", $(SUBMIT_CLASS_CONTAINER_NAME+ " .btn").outerWidth() || 250)
        .append("<i class='fa fa-spinner fa-spin fa-2x icon'></i>");
        $(SUBMIT_CLASS_CONTAINER_NAME+" [type='submit']").on("click", function() {
            $(this).closest(SUBMIT_CLASS_CONTAINER_NAME).addClass("active");
        });
    }
});
