/*
 * Development Utility for development tasks
 * prerequisites to run in local instance:
 * nodeJS virtual environment install via pip nodeenv
 * install NPM (node package manager)
 * install all required modules (i.e. run npm install in the directory containing package.json)
 * for compiling less file, run specific task to compile each respective portal less file, e.g. gulp --gulpfile less_css_gulpfile.js [task name]
 * Running each compiling task will generate sourcemap for each less to css mappings
 */

const {series, parallel, watch, src, dest} = require("gulp");
const sourcemaps = require("gulp-sourcemaps");
const rootPath = "./";
const EDPath = rootPath + "/exercise_diet/";
const GILPath = rootPath + "/gil/";
const EPROMSPath = rootPath + "/eproms/";
const lessPath = rootPath + "static/less";
const cssPath = rootPath + "static/css";
const mapPath = rootPath + "static/maps";
const less = require("gulp-less");
const replace = require("replace-in-file");
const GIL = "gil";
const PORTAL = "portal";
const EPROMS = "eproms";
const TOPNAV = "topnav";
const PORTAL_FOOTER = "portalFooter";
const PSATRACKER = "psaTracker";
const ORGTREEVIEW = "orgTreeView";
const ED = "exerciseDiet";
//const cleancss = require("clean-css");
const postCSS = require("gulp-clean-css"); //gulp wrapper around clean-css to minify css

/*eslint no-console: off */

// fetch command line arguments
const arg = (argList => {
    let arg = {},
        a, opt, thisOpt, curOpt;
    for (a = 0; a < argList.length; a++) {

        thisOpt = argList[a].trim();
        opt = thisOpt.replace(/^\-+/, "");

        if (opt === thisOpt) {
            // argument value
            if (curOpt) {
              arg[curOpt] = opt;
            }
            curOpt = null;
        } else {
            // argument name
            curOpt = opt;
            arg[curOpt] = true;
        }
    }
    return arg;

})(process.argv);

/*
 * a workaround to replace $stdin string automatically added by gulp-less module
 */
function replaceStd(fileName) {
    if (!fileName) {
      fileName = "*";
    }
    return replace({
        files: mapPath + "/" + fileName,
        from: "../../$stdin",
        to: "",
    }).then(changes => {
        console.log("Modified files: ", (changes.map(result=>result.file)).join(", "));
    }).catch(error => {
        console.log("Error occurred: ", error);
    });
}
/*
 * transforming eproms less to css
 */
const epromsLess = function(callback) {
    console.log("Compiling EPROMS Less...");
    src(lessPath + "/" + EPROMS + ".less")
        .pipe(sourcemaps.init())
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write("../../../" + mapPath))
        .pipe(dest(EPROMSPath + cssPath));
    callback();
};
exports.epromsLess = series(epromsLess);
/*
 * transforming portal less to css
 */
const portalLess = function(callback) {
    console.log("Compiling portal less...");
    src(lessPath + "/" + PORTAL + ".less")
        .pipe(sourcemaps.init({
            sources: [lessPath + "/" + PORTAL + ".less"]
        }))
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write("../../"+mapPath)) /* see documentation, https://www.npmjs.com/package/gulp-sourcemaps, to write external source map files, pass a path relative to the destination */
        .pipe(dest(cssPath))
        .on("end", function() {
            replaceStd(PORTAL + ".css.map");
        });
    callback();
};
exports.portalLess = series(portalLess);

/*
 * transforming GIL less to css
 */
const gilLess = function(callback) {
    console.log("Compiling GIL less...");
    src(lessPath + "/" + GIL + ".less")
        .pipe(sourcemaps.init({
            sources: [lessPath + "/" + GIL + ".less"]
        }))
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write("../../../"+mapPath)) /* note to write external source map files, pass a path relative to the destination */
        .pipe(dest(GILPath + cssPath))
        .on("end", function() {
            replaceStd(GIL + ".css.map");
        });
    callback();
};
exports.gilLess = series(gilLess);

/*
 * transforming portal wrapper/top nav less to css
 */
const topnavLess = function(callback) {
    console.log("Compiling portal wrapper less...");
    src(lessPath + "/" + TOPNAV + ".less")
        .pipe(sourcemaps.init())
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write("../../"+mapPath)) /* note to write external source map files, pass a path relative to the destination */
        .pipe(dest(cssPath))
        .on("end", function() {
            replaceStd(TOPNAV + ".css.map");
        });
    callback();

};
exports.topnavLess = series(topnavLess);


/*
 * transforming portal footer less to css
 */
const portalFooterLess = function(callback) {
    console.log("Compiling portal footer less...");
    src(lessPath + "/" + PORTAL_FOOTER + ".less")
        .pipe(sourcemaps.init())
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write(rootPath+"../maps")) /* note to write external source map files, pass a path relative to the destination */
        .pipe(dest(cssPath))
        .on("end", function() {
            replaceStd(PORTAL_FOOTER + ".css.map");
        });
    callback();

};
exports.portalFooterLess = series(portalFooterLess);


/*
 * transforming PSA tracker less to css
 */
const psaTrackerLess = function(callback) {
    console.log("Compiling PSA Tracker less...");
    src(lessPath + "/" + PSATRACKER + ".less")
        .pipe(sourcemaps.init())
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write("../../"+mapPath)) /* note to write external source map files, pass a path relative to the destination */
        .pipe(dest(cssPath))
        .on("end", function() {
            replaceStd(PSATRACKER + ".css.map");
        });
    callback();
};
exports.psaTrackerLess = series(psaTrackerLess);

/*
 * transforming organization tree view less to css, see /api/organization?tree_view=True
 */
const orgTreeViewLess = function(callback) {
    console.log("Compiling org tree less...");
    src(lessPath + "/" + ORGTREEVIEW + ".less")
        .pipe(sourcemaps.init())
        .pipe(less())
        .pipe(postCSS())
        .pipe(sourcemaps.write("../../"+mapPath)) /* note to write external source map files, pass a path relative to the destination */
        .pipe(dest(cssPath))
        .on("end", function() {
            replaceStd(ORGTREEVIEW + ".css.map");
        });
    callback();

};
exports.orgTreeViewLess = series(orgTreeViewLess);

/*
 * transforming exercise diet less to css
 */
const exerciseDietLess = function(callback) {
    console.log("Compiling Exercise & Diet Less...");
    src(lessPath + "/" + ED + ".less")
        .pipe(sourcemaps.init({
            sources: [lessPath + "/" + ED + ".less"]
        }))
        .pipe(less())
        .pipe(postCSS())
         /* note to write external source map files, pass a path relative to the destination
            in this case, relative to the css directory for exercise and diet
         */
        .pipe(sourcemaps.write(rootPath+"../../../"+mapPath))
        .pipe(dest(EDPath + cssPath))
        .on("end", function() {
            replaceStd(ED + ".css.map");
        });
    callback();
};
exports.exerciseDietLess = series(exerciseDietLess);

/*
 * the following tasks watch for less file changes and recompile css for each
 */
//portal
const watchPortalLess = () => {
    watch(lessPath + "/" + PORTAL + ".less", {delay: 200}, portalLess);
};
exports.watchPortalLess = series(watchPortalLess);

//eproms
const watchEpromsLess = () => {
    watch(lessPath + "/" + EPROMS + ".less", {delay: 200}, epromsLess);
};
exports.watchEpromsLess = series(watchEpromsLess);

//GIL
const watchGILLess = () => {
    watch(lessPath + "/" + GIL + ".less", {delay: 200}, gilLess);
};
exports.watchGILLess = series(watchGILLess);

//portal wrapper
const watchTopNavLess = () => {
    watch(lessPath + "/topnav.less", {delay: 200}, topnavLess);
};
exports.watchTopNavLess = series(watchTopNavLess);

//watch portal footer less
const watchPortalFooterLess = () => {
    watch(lessPath + "/" + PORTAL_FOOTER + ".less", {delay: 200}, portalFooterLess);
};
exports.watchPortalFooterLess = series(watchPortalFooterLess);

//watch exercise diet
const watchExerciseDietLess = () => {
    watch(lessPath + "/" + ED + ".less", {delay: 200}, exerciseDietLess);
};
exports.watchExerciseDietLess = series(watchExerciseDietLess);

//watch psa tracker
const watchPsaTrackerLess = () => {
    watch(lessPath + "/" + PSATRACKER + ".less", {delay: 200}, psaTrackerLess);
};
exports.watchPsaTrackerLess = series(watchPsaTrackerLess);

/*
 * compile all portal less files
 */
exports.lessAll = series(parallel(epromsLess, portalLess, topnavLess, portalFooterLess, gilLess, psaTrackerLess, orgTreeViewLess, exerciseDietLess));
