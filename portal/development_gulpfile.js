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
const uglify = require("gulp-uglifyes");
const sourcemaps = require("gulp-sourcemaps");
const rootPath = "static";
const jsPath = rootPath + "/js";
const jsDest = rootPath + "/js/dist";
const lessPath = rootPath + "/less";
const cssPath = rootPath + "/css";
const mapPath = rootPath + "/maps";
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
const jsMainFiles = [jsPath + "/i18next-config.js", jsPath + "/utility.js", jsPath + "/main.js"];

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
 * NOT currently implemented
 * concat and minify main source files to be consumed in production ??
 * call 'npm run-script build' will build minify script file, if need to 
 */
gulp.task("main", function() {
    return gulp.src(jsMainFiles)
        .pipe(concat("scripts.js"))
        .pipe(gulp.dest(jsDest))
        .pipe(rename("scripts.min.js"))
        .pipe(sourcemaps.init())
        .pipe(uglify({
            mangle: false,
            ecma: 6
        }))
        .on("error", function(err) {
            gutil.log(gutil.colors.red("[Error]"), err.toString());
        })
        .pipe(sourcemaps.write("../../maps")) //path relative to the source file, can't use rootPath here
        .pipe(gulp.dest(jsDest));
});

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
        .pipe(gulp.dest(EPROMS + "/" + cssPath));
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
        .pipe(sourcemaps.write("../maps")) //path relative to the source file, can't use rootPath here
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
        .pipe(sourcemaps.init())
        .pipe(postCSS())
        .pipe(rename(GIL + ".css"))
        .pipe(sourcemaps.write("../../../"+mapPath)) //path relative to the source file
        .pipe(gulp.dest("gil/" + cssPath))
        .on("end", function() {
            replaceStd(GIL + ".css.map")
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
        .pipe(sourcemaps.write("../maps"))
        .pipe(gulp.dest(cssPath))
        .on("end", function() {
            replaceStd(TOPNAV + ".css.map");
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
