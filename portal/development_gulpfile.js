/*
 * Development Utility for development tasks
 * prerequisites to run in local instance:
 * nodeJS virtual environment install via pip nodeenv
 * install NPM (node package manager)
 * install all required modules (i.e. run npm install in the directory containing package.json)
 * for compiling less file, run specific task to compile each respective portal less file, e.g. gulp --gulpfile less_css_gulpfile.js [task name]
 * Running each compiling task will generate sourcemap for each less to css mappings
 */
const gulp = require("gulp");
const concat = require("gulp-concat");
const rename = require("gulp-rename");
const sourcemaps = require("gulp-sourcemaps");
const rootPath = "./";
const GILPath = rootPath + "/gil/";
const EPROMSPath = rootPath + "/eproms/";
const jsPath = rootPath + "static/js";
const jsSrc = rootPath + "static/js/src";
const jsDest = rootPath + "static/js/dist";
const lessPath = rootPath + "static/less";
const cssPath = rootPath + "static/css";
const mapPath = rootPath + "static/maps";
const gutil = require("gulp-util");
const jshint = require("gulp-jshint");
const less = require("gulp-less");
const LessPluginCleanCSS = require("less-plugin-clean-css"),
    cleancss = new LessPluginCleanCSS({
        advanced: true
    });
const replace = require("replace-in-file");
const postCSS = require("gulp-clean-css");
const GIL = "gil";
const PORTAL = "portal";
const EPROMS = "eproms";
const TOPNAV = "topnav";
const PSATRACKER = "psaTracker";
const jsMainFiles = [jsSrc];

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

//linting JS
/*
 * note can pass command line argument for a particular js file to lint
 * example: gulp jshint --file './static/js/main.js'
 * alternatively can use eslint, see command line tool:  https://eslint.org/docs/user-guide/getting-started
 */
gulp.task("jshint", function() {
    var files = jsMainFiles;
    if (arg.file) {
      files = [arg.file];
    }
    return gulp.src(files)
        .pipe(jshint())
        .pipe(jshint.reporter("jshint-stylish"));
});

//for development, any change in JS mail files will resulted in scripts task being run
gulp.task("watchJS", function() {
    gulp.watch(jsMainFiles, ["jshint"]);
});

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
        console.log("Modified files: ", changes.join(", "));
    }).catch(error => {
        console.log("Error occurred: ", error);
    });
}
/*
 * transforming eproms less to css
 */
gulp.task("epromsLess", function() {
    return gulp.src(lessPath + "/" + EPROMS + ".less")
        .pipe(sourcemaps.init())
        .pipe(less({
            plugins: [cleancss]
        }))
        .pipe(sourcemaps.write("../../../" + mapPath))
        .pipe(gulp.dest(EPROMSPath + cssPath));
});
/*
 * transforming portal less to css
 */
gulp.task("portalLess", function() {
    gulp.src(lessPath + "/" + PORTAL + ".less")
        .pipe(sourcemaps.init({
            sources: [lessPath + "/" + PORTAL + ".less"]
        }))
        .pipe(less({
            plugins: [cleancss]
        }))
        .pipe(sourcemaps.write("../../"+mapPath)) /* see documentation, https://www.npmjs.com/package/gulp-sourcemaps, to write external source map files, pass a path relative to the destination */
        .pipe(gulp.dest(cssPath))
        .on("end", function() {
            replaceStd(PORTAL + ".css.map");
        });
    return true;
});
/*
 * transforming GIL less to css
 */
gulp.task("gilLess", () => {
    gulp.src(lessPath + "/" + GIL + ".less")
        .pipe(sourcemaps.init({
            sources: [lessPath + "/" + GIL + ".less"]
        }))
        .pipe(less({
            plugins: [cleancss]
        }))
        .pipe(sourcemaps.write("../../../"+mapPath)) /* note to write external source map files, pass a path relative to the destination */
        .pipe(gulp.dest(GILPath + cssPath))
        .on("end", function() {
            replaceStd(GIL + ".css.map");
        });
    return true;
});
/*
 *transforming portal wrapper/top nav less to css
 */

gulp.task("topnavLess", function() {
    gulp.src(lessPath + "/" + TOPNAV + ".less")
        .pipe(sourcemaps.init())
        .pipe(less({
            plugins: [cleancss]
        }))
        .pipe(sourcemaps.write("../../"+mapPath)) /* note to write external source map files, pass a path relative to the destination */
        .pipe(gulp.dest(cssPath))
        .on("end", function() {
            replaceStd(TOPNAV + ".css.map");
        });
    return true;
});

gulp.task("psaTrackerLess", function() {
    gulp.src(lessPath + "/" + PSATRACKER + ".less")
        .pipe(sourcemaps.init())
        .pipe(less({
            plugins: [cleancss]
        }))
        .pipe(sourcemaps.write({destPath: mapPath}))
        .pipe(gulp.dest(cssPath))
        .on("end", function() {
            replaceStd(PSATRACKER + ".css.map");
        });
    return true;
});
/*
 * running watch task will update css automatically in vivo
 * useful during development
 */
gulp.task("watchEproms", function() {
    gulp.watch(lessPath + "/eproms.less", ["epromsLess"]);
});
gulp.task("watchPortal", function() {
    gulp.watch(lessPath + "/portal.less", ["portalLess"]);
});
gulp.task("watchGil", function() {
    gulp.watch(lessPath + "/gil.less", ["gilLess"]);
});
gulp.task("watchTopnav", function() {
    gulp.watch(lessPath + "/topnav.less", ["topnavLess"]);
});
gulp.task("watchPsaTracker", function() {
    gulp.watch(lessPath + "/" + PSATRACKER + ".less", ["psaTrackerLess"]);
});
gulp.task("lessAll", ["epromsLess", "portalLess", "topnavLess", "gilLess", "psaTrackerLess"], function() {
    console.log("Compiling less files completed.");
});
