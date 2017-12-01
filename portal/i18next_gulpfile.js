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
var using = require('gulp-using');
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
const epromsNameSpace = 'eproms';
const truenthNameSpace = 'truenth';
const srcPotFileName = translationSourceDir+nameSpace+'.pot';
const epromsSrcPotFileName =  translationSourceDir+epromsNameSpace+'.pot';
const truenthSrcPotFileName = translationSourceDir+truenthNameSpace+'.pot';

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
    return gulp.src(['static/**/*.{js,html}', 'templates/*.html'])
               .pipe(scanner({
                    keySeparator: '|',
                    nsSeparator: '|',
                    attr: {
                        list: ['data-i18n'],
                        extensions: ['.js', '.html', '.htm']
                    },
                    func: {
                        list: ['i18next.t', 'i18n.t'],
                        extensions: ['.js', '.jsx', '.html', '.htm']
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: './src/' + nameSpace + '.json'
                    },
                    interpolation: {
                        prefix: '{',
                        suffix: '}'
                    }
                }))
              .pipe(gulp.dest('translations/js'));
});


/*
 * extracting text from  Eproms html files into json file
 */
gulp.task('i18next-extraction-eproms', ['clean-eproms-src'], function() {
    console.log('extracting text and generate json file ...');
    return gulp.src(['eproms/templates/eproms/*.html'])
               .pipe(scanner({
                    keySeparator: '|',
                    nsSeparator: '|',
                    attr: {
                        list: ['data-i18n'],
                        extensions: ['.js', '.html', '.htm']
                    },
                    func: {
                        list: ['i18next.t', 'i18n.t'],
                        extensions: ['.js', '.jsx', '.html', '.htm']
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: './src/' + epromsNameSpace + '.json'
                    },
                    interpolation: {
                        prefix: '{',
                        suffix: '}'
                    }
                }))
              .pipe(gulp.dest('translations/js'));
});


/*
 * extracting text from TrueNTH html files into json file
 */
gulp.task('i18next-extraction-truenth', ['clean-truenth-src'], function() {
    console.log('extracting text and generate json file ...');
    return gulp.src(['gil/templates/gil/*.html'])
               .pipe(scanner({
                    keySeparator: '|',
                    nsSeparator: '|',
                    attr: {
                        list: ['data-i18n'],
                        extensions: ['.js', '.html', '.htm']
                    },
                    func: {
                        list: ['i18next.t', 'i18n.t'],
                        extensions: ['.js', '.jsx', '.html', '.htm']
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: './src/' + truenthNameSpace + '.json'
                    },
                    interpolation: {
                        prefix: '{',
                        suffix: '}'
                    }
                }))
              .pipe(gulp.dest('translations/js'));
});

/*
 * convert eproms json to pot (the definition file) for translator's consumption
 */
gulp.task('i18nextConvertEpromsJSONToPOT', ['i18next-extraction-eproms'], function() {

    const options = {/* you options here */}
   /*
    * converting json to pot
    */
   console.log('converting Eproms JSON to POT...');
   return i18nextConv.i18nextToPot('en', fs.readFileSync(translationSourceDir+epromsNameSpace+'.json'), options).then(save(epromsSrcPotFileName));

});

/*
 * convert TrueNTH json to pot (the definition file) for translator's consumption
 */
gulp.task('i18nextConvertTruenthJSONToPOT', ['i18next-extraction-truenth'], function() {

    const options = {/* you options here */}
   /*
    * converting json to pot
    */
   console.log('converting Truenth JSON to POT...');
   return i18nextConv.i18nextToPot('en', fs.readFileSync(translationSourceDir+truenthNameSpace+'.json'), options).then(save(truenthSrcPotFileName));

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
                let messageFilePath = __path + '/' + file + '/LC_MESSAGES/messages.po';
                let frontendPoFilePath = __path + '/' + file + '/LC_MESSAGES/frontend.po';

                let epromsPoFilePath = __path + '/' + file + '/LC_MESSAGES/eproms.po';
                let truenthPoFilePath = __path + '/' + file + '/LC_MESSAGES/truenth.po';


                let destDir = translationDestinationDir+(file.replace('_', '-'));
                let messagePoExisted = fs.existsSync(messageFilePath);
                let frontendPoExisted = fs.existsSync(frontendPoFilePath);
                let epromsPoExisted = fs.existsSync(epromsPoFilePath);
                let truenthPoExisted = fs.existsSync(truenthPoFilePath);

                if (!fs.existsSync(destDir)){
                    fs.mkdirSync(destDir);
                };

                if (messagePoExisted) {
                  /*
                   * write corresponding json file from each messages po file
                   */
                  console.log('messages po file found for locale: ' + file);
                  console.log('destionation directory: ', destDir);
                  i18nextConv.gettextToI18next(file, fs.readFileSync(messageFilePath), false)
                  .then(save(destDir+'/messages.json'));
                };

                if (frontendPoExisted) {
                  /*
                   * write corresponding json file from each frontend po file
                   */
                  console.log('frontend po file found for locale: ' + file);
                  console.log('destionation directory: ', destDir);
                  i18nextConv.gettextToI18next(file, fs.readFileSync(frontendPoFilePath), false)
                  .then(save(destDir+'/frontend.json'));
                };


                if (epromsPoExisted) {
                  /*
                   * write corresponding json file from each eproms po file
                   */
                  console.log('eproms po file found for locale: ' + file);
                  console.log('destionation directory: ', destDir);
                  i18nextConv.gettextToI18next(file, fs.readFileSync(epromsPoFilePath), false)
                  .then(save(destDir+'/' + epromsNameSpace +'.json'));
                };


                if (truenthPoExisted) {
                  /*
                   * write corresponding json file from each truenth po file
                   */
                  console.log('truenth po file found for locale: ' + file);
                  console.log('destionation directory: ', destDir);
                  i18nextConv.gettextToI18next(file, fs.readFileSync(truenthPoFilePath), false)
                  .then(save(destDir+'/' + truenthNameSpace +'.json'));
                };
              };
          });
      });
  });
});


/*
 * combining each json file in each locale folder into one file, translation.json, to be consumed by the frontend
 * note this task will need to be run after i18nextConvertPOToJSON task, which creates json files from po files
 */
gulp.task('combineTranslationJsons', function() {
  console.log('combining json files ...');
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
                let messageFilePath = __path + '/' + file + '/LC_MESSAGES/messages.po';
                let frontendPoFilePath = __path + '/' + file + '/LC_MESSAGES/frontend.po';

                let epromsPoFilePath = __path + '/' + file + '/LC_MESSAGES/eproms.po';
                let truenthPoFilePath = __path + '/' + file + '/LC_MESSAGES/truenth.po';


                let destDir = translationDestinationDir+(file.replace('_', '-'));
                let messagePoExisted = fs.existsSync(messageFilePath);
                let frontendPoExisted = fs.existsSync(frontendPoFilePath);
                let epromsPoExisted = fs.existsSync(epromsPoFilePath);
                let truenthPoExisted = fs.existsSync(truenthPoFilePath);

                /*
                 * merge json files into one for frontend to consume
                 * note this plug-in will remove duplicate entries
                 */
                if (messagePoExisted || frontendPoExisted || epromsPoExisted || truenthPoExisted) {
                  console.log('merge json files...');
                  console.log("destionation: " + destDir)
                  gulp.src(destDir +'/*.json')
                    .pipe(using({}))
                    .pipe(merge_json({
                      fileName: 'translation.json'
                    }))
                    .pipe(gulp.dest(destDir));
                  
                };
              };
          });
      });
  });
});

/*
 * clean eproms source file
 */
gulp.task('clean-eproms-src', function() {
  console.log('delete source files...')
  return del([translationSourceDir + 'eproms.json']);
});


/*
 * clean truenth source file
 */
gulp.task('clean-truenth-src', function() {
  console.log('delete source files...')
  return del([translationSourceDir + 'truenth.json']);
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
 * convert eproms translation json file to pot file
 */
gulp.task('eproms', ['i18nextConvertEpromsJSONToPOT'], function() {
  console.log("Running eproms translation task...");
});

/*
 * convert truenth translation json file to pot file
 */
gulp.task('truenth', ['i18nextConvertTruenthJSONToPOT'], function() {
  console.log("Running truenth translation task...");
});


/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have
   it return the po files
   so probably should run 'i18nextConvertPOToJSON' task separately
 */
gulp.task('default', ['i18nextConvertJSONToPOT'], function() {
    console.log('running default task..');
});