/*
 * Development Utility for development tasks
 * prerequisites to run in local instance:
 * nodeJS virtual environment install via pip nodeenv
 * install NPM (node package manager)
 * install all required modules (i.e. run npm install in the directory containing package.json)
 * for compiling less file, run specific task to compile each respective portal less file, e.g. gulp --gulpfile development_gulpfile.mjs [task name]
 * Running each compiling task will generate sourcemap for each less to css mappings
 */

import { series, parallel, watch, src, dest } from "gulp";
import sourcemaps from "gulp-sourcemaps";
import less from "gulp-less";
import { replaceInFileSync } from "replace-in-file";
import postCSS from "gulp-clean-css"; // gulp wrapper around clean-css to minify css

const rootPath = "./";
const EDPath = rootPath + "/exercise_diet/";
const GILPath = rootPath + "/gil/";
const EPROMSPath = rootPath + "/eproms/";
const lessPath = rootPath + "static/less";
const cssPath = rootPath + "static/css";
const mapPath = rootPath + "static/maps";

const GIL = "gil";
const PORTAL = "portal";
const EPROMS = "eproms";
const TOPNAV = "topnav";
const PORTAL_FOOTER = "portalFooter";
const PSATRACKER = "psaTracker";
const ORGTREEVIEW = "orgTreeView";
const ED = "exerciseDiet";

/*eslint no-console: off */

// fetch command line arguments
const arg = ((argList) => {
  let arg = {},
    curOpt;
  for (let i = 0; i < argList.length; i++) {
    const thisOpt = argList[i].trim();
    const opt = thisOpt.replace(/^\-+/, "");
    if (opt === thisOpt) {
      if (curOpt) arg[curOpt] = opt;
      curOpt = null;
    } else {
      curOpt = opt;
      arg[curOpt] = true;
    }
  }
  return arg;
})(process.argv);

function replaceStd(fileName = "*") {
  let results;
  try {
    results = replaceInFileSync({
      files: `${mapPath}/${fileName}`,
      from: "../../$stdin",
      to: "",
    });
    console.log("File replacement results:", results);
  } catch (e) {
    console.error("Error occurred in file replacements:", error);
  }
  return results;
}

function epromsLessTask(callback) {
  console.log("Compiling EPROMS Less...");
  src(`${lessPath}/${EPROMS}.less`)
    .pipe(sourcemaps.init())
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`../../../${mapPath}`))
    .pipe(dest(`${EPROMSPath}${cssPath}`));
  callback();
}
export const epromsLess = series(epromsLessTask);

function portalLessTask(callback) {
  console.log("Compiling portal less...");
  src(`${lessPath}/${PORTAL}.less`)
    .pipe(sourcemaps.init({ sources: [`${lessPath}/${PORTAL}.less`] }))
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`../../${mapPath}`))
    .pipe(dest(cssPath))
    .on("end", () => replaceStd(`${PORTAL}.css.map`));
  callback();
}
export const portalLess = series(portalLessTask);

function gilLessTask(callback) {
  console.log("Compiling GIL less...");
  src(`${lessPath}/${GIL}.less`)
    .pipe(sourcemaps.init({ sources: [`${lessPath}/${GIL}.less`] }))
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`../../../${mapPath}`))
    .pipe(dest(`${GILPath}${cssPath}`))
    .on("end", () => replaceStd(`${GIL}.css.map`));
  callback();
}
export const gilLess = series(gilLessTask);

function topnavLessTask(callback) {
  console.log("Compiling portal wrapper less...");
  src(`${lessPath}/${TOPNAV}.less`)
    .pipe(sourcemaps.init())
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`../../${mapPath}`))
    .pipe(dest(cssPath))
    .on("end", () => replaceStd(`${TOPNAV}.css.map`));
  callback();
}
export const topnavLess = series(topnavLessTask);

function portalFooterLessTask(callback) {
  console.log("Compiling portal footer less...");
  src(`${lessPath}/${PORTAL_FOOTER}.less`)
    .pipe(sourcemaps.init())
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`${rootPath}../maps`))
    .pipe(dest(cssPath))
    .on("end", () => replaceStd(`${PORTAL_FOOTER}.css.map`));
  callback();
}
export const portalFooterLess = series(portalFooterLessTask);

function psaTrackerLessTask(callback) {
  console.log("Compiling PSA Tracker less...");
  src(`${lessPath}/${PSATRACKER}.less`)
    .pipe(sourcemaps.init())
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`../../${mapPath}`))
    .pipe(dest(cssPath))
    .on("end", () => replaceStd(`${PSATRACKER}.css.map`));
  callback();
}
export const psaTrackerLess = series(psaTrackerLessTask);

function orgTreeViewLessTask(callback) {
  console.log("Compiling org tree less...");
  src(`${lessPath}/${ORGTREEVIEW}.less`)
    .pipe(sourcemaps.init())
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`../../${mapPath}`))
    .pipe(dest(cssPath))
    .on("end", () => replaceStd(`${ORGTREEVIEW}.css.map`));
  callback();
}
export const orgTreeViewLess = series(orgTreeViewLessTask);

function exerciseDietLessTask(callback) {
  console.log("Compiling Exercise & Diet Less...");
  src(`${lessPath}/${ED}.less`)
    .pipe(sourcemaps.init({ sources: [`${lessPath}/${ED}.less`] }))
    .pipe(less())
    .pipe(postCSS())
    .pipe(sourcemaps.write(`${rootPath}../../../${mapPath}`))
    .pipe(dest(`${EDPath}${cssPath}`))
    .on("end", () => replaceStd(`${ED}.css.map`));
  callback();
}
export const exerciseDietLess = series(exerciseDietLessTask);

// Watchers
export const watchPortalLess = series(() =>
  watch(`${lessPath}/${PORTAL}.less`, { delay: 200 }, portalLess)
);
export const watchEpromsLess = series(() =>
  watch(`${lessPath}/${EPROMS}.less`, { delay: 200 }, epromsLess)
);
export const watchGILLess = series(() =>
  watch(`${lessPath}/${GIL}.less`, { delay: 200 }, gilLess)
);
export const watchTopNavLess = series(() =>
  watch(`${lessPath}/${TOPNAV}.less`, { delay: 200 }, topnavLess)
);
export const watchPortalFooterLess = series(() =>
  watch(`${lessPath}/${PORTAL_FOOTER}.less`, { delay: 200 }, portalFooterLess)
);
export const watchExerciseDietLess = series(() =>
  watch(`${lessPath}/${ED}.less`, { delay: 200 }, exerciseDietLess)
);
export const watchPsaTrackerLess = series(() =>
  watch(`${lessPath}/${PSATRACKER}.less`, { delay: 200 }, psaTrackerLess)
);

export const lessAll = series(
  parallel(
    epromsLess,
    portalLess,
    topnavLess,
    portalFooterLess,
    gilLess,
    psaTrackerLess,
    orgTreeViewLess,
    exerciseDietLess
  )
);

export default lessAll;
