/*
 * prerequisites:
 * nodeJS virtual environment install via pip nodeenv
 * install NPM (node package manager)
 * install all required modules (i.e. run npm install in the directory containing package.json)
 * run gulp --gulpfile i18next_gulpfile.js will perform default task -
 * which will perform text extraction and translate resulting json to pot file
 * run gulp --gulpfile i18next_gulpfile.js [task name]  will run individual task
 * NB:  should NOT run this in Production environment, the resulting modules in node_modules/ folder from running `npm install` should never be checked in
 */
var gulp = require('gulp');
var source = require('vinyl-source-stream');
var request = require('request');
var merge = require('merge2');
var buffer = require('gulp-buffer');
var del = require('del');
var scanner = require('i18next-scanner');
var concatPo = require('gulp-concat-po');
var merge_json = require('gulp-merge-json');
const path = require('path');
const fs = require('fs');
const i18nextConv = require('i18next-conv');
/*
 * where the generated json/pot files from extraction of js files will reside
 */
const translationSourceDir = path.join(__dirname, './translations/js/src/');
/*
 * the path to the converted json file from po file of corresponding locale
 * JS files will consume the translated text from here
 * note json files are saved for each specific locale
 */
const translationDestinationDir = path.join(__dirname,'./static/files/locales/');
/*
 * namespace
 */
const nameSpace = 'frontend';
const srcPotFileName = translationSourceDir+nameSpace+'.pot';

/*
 * helper function for writing file
 */
function save(target) {
  return result => {
    fs.writeFileSync(target, result);
  };
};

/*
 * extracting text from js/html files into json file
 */
gulp.task('i18next-extraction', ['clean-src'], function() {
    console.log('extracting text and generate json file ...');
    return gulp.src(['static/**/*.{js,html}'])
               .pipe(scanner({
                    keySeparator: "|",
                    nsSeparator: "|",
                    attr: {
                        list: ['data-i18n'],
                        extensions: ['.js', '.html', '.htm']
                    },
                    func: {
                        list: ['i18next.t', 'i18n.t'],
                        extensions: ['.js', '.jsx']
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: './src/' + nameSpace + '.json'
                    }
                }))
              .pipe(gulp.dest('translations/js'));
});

/*
 * convert json to pot (the definition file) for translator's consumption
 */
gulp.task('i18nextConvertJSONToPOT', ['i18next-extraction'], function() {

    const options = {/* you options here */}
    /*
     * allow for multiple json tranlsation files
     */
    gulp.src(translationSourceDir+'*.json')
        .pipe(merge_json({fileName: nameSpace+'.json'}))
        .pipe(gulp.dest(translationSourceDir));
   /*
    * converting json to pot
    */
   console.log('converting JSON to POT...');
   return i18nextConv.i18nextToPot('en', fs.readFileSync(translationSourceDir+nameSpace+'.json'), options).then(save(srcPotFileName));

});

gulp.task('combineSrcJson', function() {
    /*
     * allow for multiple json tranlsation files
     */
    if (fs.existsSync('translations/js/src/custom.json')) console.log("exists")
    gulp.src('translations/js/src/*.json')
        .pipe(merge_json({fileName: 'test.json'}))
        .pipe(gulp.dest('translations/js/src'));

});

/*
 * combine newly created pot file to existing messages.pot file ???
 * do we need this step??
 */
gulp.task('combineAllPotFiles', ['i18nextConvertJSONToPOT'], function() {
    console.log("combine all pot files ...")
    return gulp.src([srcPotFileName, 'translations/messages.pot'])
          .pipe(concatPo('messages.pot'))
          .pipe(gulp.dest('translations'));
});

/*
 * converting po to json files
 * note translating existing po file to json, which will be consumed by the front end
 * this task assumes that:
 *    1. text has been extracted from js file into JSON file
 *    2. translated JSON into POT
 *    3. Po files have been returned from translator after uploading POT file from #2
 */
gulp.task('i18nextConvertPOToJSON', ['clean-dest'], function() {
  console.log('converting po to json ...');
  const options = {/* you options here */}
   /*
    * translating po file to json for supported languages
    */
  var __path = path.join(__dirname,'./translations');
  return fs.readdir(__path, function(err, files) {
      files.forEach(function(file) {
          let filePath = __path + '/' + file;
          fs.stat(filePath, function(err, stat) {
              if (stat.isDirectory()) {
                /*
                 * directories are EN_US, EN_AU, etc.
                 * so check to see if each has a PO file
                 */
                let poFilePath = __path + '/' + file + '/LC_MESSAGES/messages.po';
                let fpoFilePath = __path + '/' + file + '/LC_MESSAGES/frontend.po';
                let destDir = translationDestinationDir+file.replace('_', '-');
                let poExisted = fs.existsSync(poFilePath);
                let fpoExisted = fs.existsSync(fpoFilePath);

                if (!fs.existsSync(destDir)){
                    fs.mkdirSync(destDir);
                };

                if (poExisted && fpoExisted) {
                    console.log('messages po locale found: ' + file);
                    /*
                     * write corresponding json file from each messages po file
                     */
                    i18nextConv.gettextToI18next(file, fs.readFileSync(poFilePath), false)
                    .then(save(destDir+'/messages.json'));

                    console.log('frontend po locale found: ' + file);
                    /*
                     * write corresponding json file from each frontend po file
                     */
                    i18nextConv.gettextToI18next(file, fs.readFileSync(fpoFilePath), false)
                    .then(save(destDir+'/frontend.json'));

                    console.log("merge json files to translation.json..");
                    /*
                     * merge json files into one for frontend to consume
                     * note this plug-in will remove duplicate entries
                     */
                    gulp.src(destDir+'/*.json')
                    .pipe(merge_json({
                      fileName: 'translation.json'
                    }))
                    .pipe(gulp.dest(destDir));
                } else if (poExisted) {
                    console.log('messages po locale found: ' + file + ' in ' + poFilePath);
                    /*
                     * write corresponding json file from each messages po file
                     */
                    i18nextConv.gettextToI18next(file, fs.readFileSync(poFilePath), false)
                    .then(save(destDir+'/translation.json'));
                } else if (fpoExisted) {
                    console.log('frontend po locale found: ' + file);
                    /*
                     * write corresponding json file from each frontend po file
                     */
                    i18nextConv.gettextToI18next(file, fs.readFileSync(fpoFilePath), false)
                    .then(save(destDir+'/translation.json'));
                };
              };
          });
      });
  });
});

/*
 * clean all generated source files
 */
gulp.task('clean-src', function() {
  console.log('delete source files...')
  return del([translationSourceDir + nameSpace + '.json']);
});

/*
 * clean all generated destination json files
 */
gulp.task('clean-dest', function() {
  console.log('delete json files...')
  return del([translationDestinationDir + '*/*.json']);
});


/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have
   it return the po files
   so probably should run 'i18nextConvertPOToJSON' task separately
 */
gulp.task('default', ['i18nextConvertJSONToPOT'], function() {
    console.log('running default task..');
});