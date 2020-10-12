export default {
    methods: {
        initVideo() {
            let videoElement = document.querySelector(".video");
            if (!videoElement) {
                return;
            }
            let iframeElement = document.createElement("iframe");
            iframeElement.setAttribute("allowfullscreen", true);
            iframeElement.setAttribute("src", videoElement.getAttribute("data-iframe-src"));
            videoElement.appendChild(iframeElement);
            videoElement.classList.add("active");
            let videoNavElements = document.querySelectorAll(".navigation-video-image");
            videoNavElements.forEach(el => {
                el.addEventListener("click", () => {
                    let ve = document.querySelector(".video iframe");
                    if (ve) {
                        let veSrc = ve.getAttribute("src");
                        if (veSrc.indexOf("?") !== -1) {
                            veSrc = veSrc.substring(0, veSrc.indexOf("?"));
                        }
                        ve.setAttribute("src", veSrc + "?autoPlay=true");
                    }
                });
                el.classList.remove("hide");
            });
        }
    }
}
