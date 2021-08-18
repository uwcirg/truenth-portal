$(function() {
    var handleCollapsible = function() {
        var collapsibleElements = document.querySelectorAll(".collapsible");
        for (var index = 0; index < collapsibleElements.length; index ++) {
            var el = collapsibleElements[index];
            el.addEventListener('click', function(event) {
                var targetElement = $(event.target).closest(".collapsible");
                var parentEl = targetElement[0].parentElement.parentElement;
                var collapsibleItems = parentEl.querySelectorAll(".collapsible");
                for (var subindex = 0; subindex < collapsibleItems.length; subindex++) {
                    var item = collapsibleItems[subindex];
                    if (item === targetElement[0]) continue;
                    item.classList.remove("open");
                }
                if (targetElement[0].classList.contains("open")) {
                    targetElement[0].classList.remove("open");
                    return;
                }
                targetElement[0].classList.add("open");
                targetElement[0].scrollIntoView();
            });
        }
    }
    handleCollapsible();
});
