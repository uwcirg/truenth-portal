// Kiosk API of KP Enterprise (7.8.5345)

if (typeof(___kp_executeURL) !== "function")
{
	// Common JS-ObjC-Bridge API:
	function ___kp_executeURL(url)
	{
		var iframe = document.createElement("IFRAME");
		iframe.setAttribute("src", url);
		document.documentElement.appendChild(iframe);
		iframe.parentNode.removeChild(iframe);
		iframe = null;
	}
}


if (typeof(_kp_frames_special_) === "undefined")
{
	// iFrame support:
	var _kp_i_, _kp_frames_special_;
	_kp_frames_special_ = document.getElementsByTagName("iframe");
}

// Kiosk Version API:
if (typeof(kp_VersionAPI_requestFullVersion) !== "function")
{
	function kp_VersionAPI_requestFullVersion(callback)
	{
		___kp_executeURL("kioskpro://kp_VersionAPI_requestFullVersion?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_VersionAPI_requestFullVersion'] = function(callback) { kp_VersionAPI_requestFullVersion(callback); };
}

if (typeof(kp_VersionAPI_requestMainVersion) !== "function")
{
	function kp_VersionAPI_requestMainVersion(callback)
	{
		___kp_executeURL("kioskpro://kp_VersionAPI_requestMainVersion?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_VersionAPI_requestMainVersion'] = function(callback) { kp_VersionAPI_requestMainVersion(callback); };
}

if (typeof(kp_VersionAPI_requestBuildNumber) !== "function")
{
	function kp_VersionAPI_requestBuildNumber(callback)
	{
		___kp_executeURL("kioskpro://kp_VersionAPI_requestBuildNumber?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_VersionAPI_requestBuildNumber'] = function(callback) { kp_VersionAPI_requestBuildNumber(callback); };
}

if (typeof(kp_VersionAPI_requestProductName) !== "function")
{
	function kp_VersionAPI_requestProductName(callback)
	{
		___kp_executeURL("kioskpro://kp_VersionAPI_requestProductName?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_VersionAPI_requestProductName'] = function(callback) { kp_VersionAPI_requestProductName(callback); };
}

if (typeof(kp_VersionAPI_requestProductNameWithFullVersion) !== "function")
{
	function kp_VersionAPI_requestProductNameWithFullVersion(callback)
	{
		___kp_executeURL("kioskpro://kp_VersionAPI_requestProductNameWithFullVersion?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_VersionAPI_requestProductNameWithFullVersion'] = function(callback) { kp_VersionAPI_requestProductNameWithFullVersion(callback); };
}

// Identification API:
if (typeof(kp_requestKioskId) !== "function")
{
	function kp_requestKioskId(callback)
	{
		___kp_executeURL("kioskpro://kp_requestKioskId?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_requestKioskId'] = function(callback) { kp_requestKioskId(callback); };
}

if (typeof(kp_Identification_getGroupIDs) !== "function")
{
	function kp_Identification_getGroupIDs()
	{
		___kp_executeURL("kioskpro://kp_Identification_getGroupIDs");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_Identification_getGroupIDs'] = function() { kp_Identification_getGroupIDs(); };
}

// File API:
if (typeof(writeToFile) !== "function")
{
	function writeToFile(fileName,data,callback)
	{
		___kp_executeURL("kioskpro://writeToFile?" + encodeURIComponent(fileName) + "&" + encodeURIComponent(data) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['writeToFile'] = function(fileName,data,callback) { writeToFile(fileName,data,callback); };
}

if (typeof(fileExists) !== "function")
{
	function fileExists(filename,callback)
	{
		___kp_executeURL("kioskpro://fileExists?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['fileExists'] = function(filename,callback) { fileExists(filename,callback); };
}

if (typeof(deleteFile) !== "function")
{
	function deleteFile(filename,callback)
	{
		___kp_executeURL("kioskpro://deleteFile?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['deleteFile'] = function(filename,callback) { deleteFile(filename,callback); };
}

if (typeof(kp_FileAPI_renameFile) !== "function")
{
	function kp_FileAPI_renameFile(oldFilename,newFilename,callback)
	{
		___kp_executeURL("kioskpro://kp_FileAPI_renameFile?" + encodeURIComponent(oldFilename) + "&" + encodeURIComponent(newFilename) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_FileAPI_renameFile'] = function(oldFilename,newFilename,callback) { kp_FileAPI_renameFile(oldFilename,newFilename,callback); };
}

if (typeof(kp_FileAPI_base64FromFile) !== "function")
{
	function kp_FileAPI_base64FromFile(filename,callback)
	{
		___kp_executeURL("kioskpro://kp_FileAPI_base64FromFile?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_FileAPI_base64FromFile'] = function(filename,callback) { kp_FileAPI_base64FromFile(filename,callback); };
}

// Photo & Video API:
if (typeof(saveScreenToPng) !== "function")
{
	function saveScreenToPng(filename,x,y,width,height,callback)
	{
		___kp_executeURL("kioskpro://saveScreenToPng?" + encodeURIComponent(filename) + "&" + encodeURIComponent(x) + "&" + encodeURIComponent(y) + "&" + encodeURIComponent(width) + "&" + encodeURIComponent(height) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['saveScreenToPng'] = function(filename,x,y,width,height,callback) { saveScreenToPng(filename,x,y,width,height,callback); };
}

if (typeof(kp_PhotoVideo_setCameraType) !== "function")
{
	function kp_PhotoVideo_setCameraType(shouldUseFrontCamera,callback)
	{
		___kp_executeURL("kioskpro://kp_PhotoVideo_setCameraType?" + encodeURIComponent(shouldUseFrontCamera) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_PhotoVideo_setCameraType'] = function(shouldUseFrontCamera,callback) { kp_PhotoVideo_setCameraType(shouldUseFrontCamera,callback); };
}

if (typeof(kp_PhotoVideo_getCameraType) !== "function")
{
	function kp_PhotoVideo_getCameraType(callback)
	{
		___kp_executeURL("kioskpro://kp_PhotoVideo_getCameraType?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_PhotoVideo_getCameraType'] = function(callback) { kp_PhotoVideo_getCameraType(callback); };
}

if (typeof(takePhotoToFile) !== "function")
{
	function takePhotoToFile(filename,callback)
	{
		___kp_executeURL("kioskpro://takePhotoToFile?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['takePhotoToFile'] = function(filename,callback) { takePhotoToFile(filename,callback); };
}

if (typeof(takePhotoWithCountdownToFile) !== "function")
{
	function takePhotoWithCountdownToFile(filename,callback,counter,message,showingTime)
	{
		___kp_executeURL("kioskpro://takePhotoWithCountdownToFile?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback) + "&" + encodeURIComponent(counter) + "&" + encodeURIComponent(message) + "&" + encodeURIComponent(showingTime));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['takePhotoWithCountdownToFile'] = function(filename,callback,counter,message,showingTime) { takePhotoWithCountdownToFile(filename,callback,counter,message,showingTime); };
}

if (typeof(takeVideoToFile) !== "function")
{
	function takeVideoToFile(filename,callback)
	{
		___kp_executeURL("kioskpro://takeVideoToFile?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['takeVideoToFile'] = function(filename,callback) { takeVideoToFile(filename,callback); };
}

if (typeof(kp_PhotoVideo_takeVideoWithCountdown) !== "function")
{
	function kp_PhotoVideo_takeVideoWithCountdown(filename,callback,intervalBeforeStart,recordingTime,showRecordingCountdownTimer,successMessage)
	{
		___kp_executeURL("kioskpro://kp_PhotoVideo_takeVideoWithCountdown?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback) + "&" + encodeURIComponent(intervalBeforeStart) + "&" + encodeURIComponent(recordingTime) + "&" + encodeURIComponent(showRecordingCountdownTimer) + "&" + encodeURIComponent(successMessage));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_PhotoVideo_takeVideoWithCountdown'] = function(filename,callback,intervalBeforeStart,recordingTime,showRecordingCountdownTimer,successMessage) { kp_PhotoVideo_takeVideoWithCountdown(filename,callback,intervalBeforeStart,recordingTime,showRecordingCountdownTimer,successMessage); };
}

if (typeof(kp_PhotoVideo_takeVideoWithEndingByTouchingScreen) !== "function")
{
	function kp_PhotoVideo_takeVideoWithEndingByTouchingScreen(filename,callback,intervalBeforeStart,maxRecordingTime,messageDuringRecording,showRecordingTimer,successMessage)
	{
		___kp_executeURL("kioskpro://kp_PhotoVideo_takeVideoWithEndingByTouchingScreen?" + encodeURIComponent(filename) + "&" + encodeURIComponent(callback) + "&" + encodeURIComponent(intervalBeforeStart) + "&" + encodeURIComponent(maxRecordingTime) + "&" + encodeURIComponent(messageDuringRecording) + "&" + encodeURIComponent(showRecordingTimer) + "&" + encodeURIComponent(successMessage));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_PhotoVideo_takeVideoWithEndingByTouchingScreen'] = function(filename,callback,intervalBeforeStart,maxRecordingTime,messageDuringRecording,showRecordingTimer,successMessage) { kp_PhotoVideo_takeVideoWithEndingByTouchingScreen(filename,callback,intervalBeforeStart,maxRecordingTime,messageDuringRecording,showRecordingTimer,successMessage); };
}

// iDynamo Card Reader API:
if (typeof(kp_iDynamoCardReader_requestDeviceType) !== "function")
{
	function kp_iDynamoCardReader_requestDeviceType()
	{
		___kp_executeURL("kioskpro://kp_iDynamoCardReader_requestDeviceType");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iDynamoCardReader_requestDeviceType'] = function() { kp_iDynamoCardReader_requestDeviceType(); };
}

if (typeof(kp_iDynamoCardReader_requestStateOfConnection) !== "function")
{
	function kp_iDynamoCardReader_requestStateOfConnection()
	{
		___kp_executeURL("kioskpro://kp_iDynamoCardReader_requestStateOfConnection");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iDynamoCardReader_requestStateOfConnection'] = function() { kp_iDynamoCardReader_requestStateOfConnection(); };
}

if (typeof(kp_iDynamoCardReader_requestSwipe) !== "function")
{
	function kp_iDynamoCardReader_requestSwipe(swipeInfo)
	{
		___kp_executeURL("kioskpro://kp_iDynamoCardReader_requestSwipe?" + encodeURIComponent(swipeInfo));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iDynamoCardReader_requestSwipe'] = function(swipeInfo) { kp_iDynamoCardReader_requestSwipe(swipeInfo); };
}

if (typeof(kp_iDynamoCardReader_cancelSwipe) !== "function")
{
	function kp_iDynamoCardReader_cancelSwipe()
	{
		___kp_executeURL("kioskpro://kp_iDynamoCardReader_cancelSwipe");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iDynamoCardReader_cancelSwipe'] = function() { kp_iDynamoCardReader_cancelSwipe(); };
}

if (typeof(kp_iDynamoCardReader_mps_doCreditSaleOperation) !== "function")
{
	function kp_iDynamoCardReader_mps_doCreditSaleOperation(amount,invoiceNumber)
	{
		___kp_executeURL("kioskpro://kp_iDynamoCardReader_mps_doCreditSaleOperation?" + encodeURIComponent(amount) + "&" + encodeURIComponent(invoiceNumber));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iDynamoCardReader_mps_doCreditSaleOperation'] = function(amount,invoiceNumber) { kp_iDynamoCardReader_mps_doCreditSaleOperation(amount,invoiceNumber); };
}

// External Screen API:
if (typeof(kp_ExternalScreen_requestStateOfConnection) !== "function")
{
	function kp_ExternalScreen_requestStateOfConnection()
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_requestStateOfConnection");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_requestStateOfConnection'] = function() { kp_ExternalScreen_requestStateOfConnection(); };
}

if (typeof(kp_ExternalScreen_requestProperties) !== "function")
{
	function kp_ExternalScreen_requestProperties(callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_requestProperties?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_requestProperties'] = function(callback) { kp_ExternalScreen_requestProperties(callback); };
}

if (typeof(kp_ExternalScreen_setScreenMode) !== "function")
{
	function kp_ExternalScreen_setScreenMode(width,height,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_setScreenMode?" + encodeURIComponent(width) + "&" + encodeURIComponent(height) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_setScreenMode'] = function(width,height,callback) { kp_ExternalScreen_setScreenMode(width,height,callback); };
}

if (typeof(kp_ExternalScreen_setOverscanCompensationMode) !== "function")
{
	function kp_ExternalScreen_setOverscanCompensationMode(mode,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_setOverscanCompensationMode?" + encodeURIComponent(mode) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_setOverscanCompensationMode'] = function(mode,callback) { kp_ExternalScreen_setOverscanCompensationMode(mode,callback); };
}

if (typeof(kp_ExternalScreen_connectToScreen) !== "function")
{
	function kp_ExternalScreen_connectToScreen()
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_connectToScreen");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_connectToScreen'] = function() { kp_ExternalScreen_connectToScreen(); };
}

if (typeof(kp_ExternalScreen_disconnectFromScreen) !== "function")
{
	function kp_ExternalScreen_disconnectFromScreen()
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_disconnectFromScreen");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_disconnectFromScreen'] = function() { kp_ExternalScreen_disconnectFromScreen(); };
}

if (typeof(kp_ExternalScreen_openDocument) !== "function")
{
	function kp_ExternalScreen_openDocument(filePath,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_openDocument?" + encodeURIComponent(filePath) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_openDocument'] = function(filePath,callback) { kp_ExternalScreen_openDocument(filePath,callback); };
}

if (typeof(kp_ExternalScreen_setBrowserBgColor) !== "function")
{
	function kp_ExternalScreen_setBrowserBgColor(bgColor,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_setBrowserBgColor?" + encodeURIComponent(bgColor) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_setBrowserBgColor'] = function(bgColor,callback) { kp_ExternalScreen_setBrowserBgColor(bgColor,callback); };
}

if (typeof(kp_ExternalScreen_getBrowserBgColor) !== "function")
{
	function kp_ExternalScreen_getBrowserBgColor(callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_getBrowserBgColor?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_getBrowserBgColor'] = function(callback) { kp_ExternalScreen_getBrowserBgColor(callback); };
}

if (typeof(kp_ExternalScreen_doJScript) !== "function")
{
	function kp_ExternalScreen_doJScript(script)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_doJScript?" + encodeURIComponent(script));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_doJScript'] = function(script) { kp_ExternalScreen_doJScript(script); };
}

if (typeof(kp_ExternalScreen_setPlayVideoParams) !== "function")
{
	function kp_ExternalScreen_setPlayVideoParams(fadeDuration,fadeBgColor,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_setPlayVideoParams?" + encodeURIComponent(fadeDuration) + "&" + encodeURIComponent(fadeBgColor) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_setPlayVideoParams'] = function(fadeDuration,fadeBgColor,callback) { kp_ExternalScreen_setPlayVideoParams(fadeDuration,fadeBgColor,callback); };
}

if (typeof(kp_ExternalScreen_getPlayVideoParams) !== "function")
{
	function kp_ExternalScreen_getPlayVideoParams(callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_getPlayVideoParams?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_getPlayVideoParams'] = function(callback) { kp_ExternalScreen_getPlayVideoParams(callback); };
}

if (typeof(kp_ExternalScreen_playVideo) !== "function")
{
	function kp_ExternalScreen_playVideo(filePath,loop,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_playVideo?" + encodeURIComponent(filePath) + "&" + encodeURIComponent(loop) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_playVideo'] = function(filePath,loop,callback) { kp_ExternalScreen_playVideo(filePath,loop,callback); };
}

if (typeof(kp_ExternalScreen_getCurrentVideoPlaybackState) !== "function")
{
	function kp_ExternalScreen_getCurrentVideoPlaybackState(callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_getCurrentVideoPlaybackState?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_getCurrentVideoPlaybackState'] = function(callback) { kp_ExternalScreen_getCurrentVideoPlaybackState(callback); };
}

if (typeof(kp_ExternalScreen_stopVideo) !== "function")
{
	function kp_ExternalScreen_stopVideo()
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_stopVideo");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_stopVideo'] = function() { kp_ExternalScreen_stopVideo(); };
}

if (typeof(kp_ExternalScreen_stopVideoWithFading) !== "function")
{
	function kp_ExternalScreen_stopVideoWithFading(shouldFadeOut)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_stopVideoWithFading?" + encodeURIComponent(shouldFadeOut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_stopVideoWithFading'] = function(shouldFadeOut) { kp_ExternalScreen_stopVideoWithFading(shouldFadeOut); };
}

if (typeof(kp_ExternalScreen_pauseVideo) !== "function")
{
	function kp_ExternalScreen_pauseVideo()
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_pauseVideo");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_pauseVideo'] = function() { kp_ExternalScreen_pauseVideo(); };
}

if (typeof(kp_ExternalScreen_resumeVideo) !== "function")
{
	function kp_ExternalScreen_resumeVideo()
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_resumeVideo");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_resumeVideo'] = function() { kp_ExternalScreen_resumeVideo(); };
}

if (typeof(kp_ExternalScreen_changeCurrentTimeOfVideo) !== "function")
{
	function kp_ExternalScreen_changeCurrentTimeOfVideo(time)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_changeCurrentTimeOfVideo?" + encodeURIComponent(time));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_changeCurrentTimeOfVideo'] = function(time) { kp_ExternalScreen_changeCurrentTimeOfVideo(time); };
}

if (typeof(kp_ExternalScreen_requestNumberOfPdfPages) !== "function")
{
	function kp_ExternalScreen_requestNumberOfPdfPages(callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_requestNumberOfPdfPages?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_requestNumberOfPdfPages'] = function(callback) { kp_ExternalScreen_requestNumberOfPdfPages(callback); };
}

if (typeof(kp_ExternalScreen_showPdfPage) !== "function")
{
	function kp_ExternalScreen_showPdfPage(pageNumber,callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_showPdfPage?" + encodeURIComponent(pageNumber) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_showPdfPage'] = function(pageNumber,callback) { kp_ExternalScreen_showPdfPage(pageNumber,callback); };
}

if (typeof(kp_ExternalScreen_requestNumberOfCurrentPdfPage) !== "function")
{
	function kp_ExternalScreen_requestNumberOfCurrentPdfPage(callback)
	{
		___kp_executeURL("kioskpro://kp_ExternalScreen_requestNumberOfCurrentPdfPage?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ExternalScreen_requestNumberOfCurrentPdfPage'] = function(callback) { kp_ExternalScreen_requestNumberOfCurrentPdfPage(callback); };
}

// iMag2 Card Reader API:
if (typeof(getReaderData) !== "function")
{
	function getReaderData(callback)
	{
		___kp_executeURL("kioskpro://getReaderData?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['getReaderData'] = function(callback) { getReaderData(callback); };
}

if (typeof(kp_iMagCardReader_requestSwipe) !== "function")
{
	function kp_iMagCardReader_requestSwipe(swipeInfo)
	{
		___kp_executeURL("kioskpro://kp_iMagCardReader_requestSwipe?" + encodeURIComponent(swipeInfo));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iMagCardReader_requestSwipe'] = function(swipeInfo) { kp_iMagCardReader_requestSwipe(swipeInfo); };
}

if (typeof(kp_iMagCardReader_requestStateOfSupporting) !== "function")
{
	function kp_iMagCardReader_requestStateOfSupporting()
	{
		___kp_executeURL("kioskpro://kp_iMagCardReader_requestStateOfSupporting");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iMagCardReader_requestStateOfSupporting'] = function() { kp_iMagCardReader_requestStateOfSupporting(); };
}

if (typeof(kp_iMagCardReader_requestStateOfConnection) !== "function")
{
	function kp_iMagCardReader_requestStateOfConnection()
	{
		___kp_executeURL("kioskpro://kp_iMagCardReader_requestStateOfConnection");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_iMagCardReader_requestStateOfConnection'] = function() { kp_iMagCardReader_requestStateOfConnection(); };
}

// Memory & Privacy API:
if (typeof(kp_Browser_clearCookies) !== "function")
{
	function kp_Browser_clearCookies()
	{
		___kp_executeURL("kioskpro://kp_Browser_clearCookies");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_Browser_clearCookies'] = function() { kp_Browser_clearCookies(); };
}

if (typeof(kp_Browser_clearCache) !== "function")
{
	function kp_Browser_clearCache()
	{
		___kp_executeURL("kioskpro://kp_Browser_clearCache");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_Browser_clearCache'] = function() { kp_Browser_clearCache(); };
}

// ZBar Scanner API:
if (typeof(kp_ZBarScanner_startScan) !== "function")
{
	function kp_ZBarScanner_startScan()
	{
		___kp_executeURL("kioskpro://kp_ZBarScanner_startScan");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ZBarScanner_startScan'] = function() { kp_ZBarScanner_startScan(); };
}

if (typeof(kp_ZBarScanner_cancelScan) !== "function")
{
	function kp_ZBarScanner_cancelScan()
	{
		___kp_executeURL("kioskpro://kp_ZBarScanner_cancelScan");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ZBarScanner_cancelScan'] = function() { kp_ZBarScanner_cancelScan(); };
}

if (typeof(kp_ZBarScanner_requestStateOfSupporting) !== "function")
{
	function kp_ZBarScanner_requestStateOfSupporting()
	{
		___kp_executeURL("kioskpro://kp_ZBarScanner_requestStateOfSupporting");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_ZBarScanner_requestStateOfSupporting'] = function() { kp_ZBarScanner_requestStateOfSupporting(); };
}

// MPS API:
if (typeof(kp_MercuryPaySystem_generateFullReportToFile) !== "function")
{
	function kp_MercuryPaySystem_generateFullReportToFile(fileName,callback)
	{
		___kp_executeURL("kioskpro://kp_MercuryPaySystem_generateFullReportToFile?" + encodeURIComponent(fileName) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_MercuryPaySystem_generateFullReportToFile'] = function(fileName,callback) { kp_MercuryPaySystem_generateFullReportToFile(fileName,callback); };
}

if (typeof(kp_MercuryPaySystem_getSettings) !== "function")
{
	function kp_MercuryPaySystem_getSettings()
	{
		___kp_executeURL("kioskpro://kp_MercuryPaySystem_getSettings");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_MercuryPaySystem_getSettings'] = function() { kp_MercuryPaySystem_getSettings(); };
}

if (typeof(kp_MercuryPaySystem_requestLastRegisteredOperation) !== "function")
{
	function kp_MercuryPaySystem_requestLastRegisteredOperation()
	{
		___kp_executeURL("kioskpro://kp_MercuryPaySystem_requestLastRegisteredOperation");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_MercuryPaySystem_requestLastRegisteredOperation'] = function() { kp_MercuryPaySystem_requestLastRegisteredOperation(); };
}

// Bluetooth BarCode Scanner API:
if (typeof(kp_BluetoothBarcodeScanner_requestAcceptingData) !== "function")
{
	function kp_BluetoothBarcodeScanner_requestAcceptingData(alert_title,alert_message,wait_in_seconds)
	{
		___kp_executeURL("kioskpro://kp_BluetoothBarcodeScanner_requestAcceptingData?" + encodeURIComponent(alert_title) + "&" + encodeURIComponent(alert_message) + "&" + encodeURIComponent(wait_in_seconds));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_BluetoothBarcodeScanner_requestAcceptingData'] = function(alert_title,alert_message,wait_in_seconds) { kp_BluetoothBarcodeScanner_requestAcceptingData(alert_title,alert_message,wait_in_seconds); };
}

if (typeof(kp_BluetoothBarcodeScanner_requestSilentAcceptingData) !== "function")
{
	function kp_BluetoothBarcodeScanner_requestSilentAcceptingData()
	{
		___kp_executeURL("kioskpro://kp_BluetoothBarcodeScanner_requestSilentAcceptingData");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_BluetoothBarcodeScanner_requestSilentAcceptingData'] = function() { kp_BluetoothBarcodeScanner_requestSilentAcceptingData(); };
}

if (typeof(kp_BluetoothBarcodeScanner_requestStateOfSupporting) !== "function")
{
	function kp_BluetoothBarcodeScanner_requestStateOfSupporting()
	{
		___kp_executeURL("kioskpro://kp_BluetoothBarcodeScanner_requestStateOfSupporting");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_BluetoothBarcodeScanner_requestStateOfSupporting'] = function() { kp_BluetoothBarcodeScanner_requestStateOfSupporting(); };
}

//  Dropbox API:
if (typeof(kp_DBXSyncManager_sync) !== "function")
{
	function kp_DBXSyncManager_sync()
	{
		___kp_executeURL("kioskpro://kp_DBXSyncManager_sync");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DBXSyncManager_sync'] = function() { kp_DBXSyncManager_sync(); };
}

if (typeof(kp_DBXSyncManager_stopObservingChangesOfType) !== "function")
{
	function kp_DBXSyncManager_stopObservingChangesOfType(typeOfChanges)
	{
		___kp_executeURL("kioskpro://kp_DBXSyncManager_stopObservingChangesOfType?" + encodeURIComponent(typeOfChanges));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DBXSyncManager_stopObservingChangesOfType'] = function(typeOfChanges) { kp_DBXSyncManager_stopObservingChangesOfType(typeOfChanges); };
}

if (typeof(kp_DBXSyncManager_startObservingChangesOfType) !== "function")
{
	function kp_DBXSyncManager_startObservingChangesOfType(typeOfChanges)
	{
		___kp_executeURL("kioskpro://kp_DBXSyncManager_startObservingChangesOfType?" + encodeURIComponent(typeOfChanges));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DBXSyncManager_startObservingChangesOfType'] = function(typeOfChanges) { kp_DBXSyncManager_startObservingChangesOfType(typeOfChanges); };
}

if (typeof(kp_DBXSyncManager_getTypeOfObservingChanges) !== "function")
{
	function kp_DBXSyncManager_getTypeOfObservingChanges(callback)
	{
		___kp_executeURL("kioskpro://kp_DBXSyncManager_getTypeOfObservingChanges?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DBXSyncManager_getTypeOfObservingChanges'] = function(callback) { kp_DBXSyncManager_getTypeOfObservingChanges(callback); };
}

// Audio Player API:
if (typeof(kp_AudioPlayer_play) !== "function")
{
	function kp_AudioPlayer_play(filePath,atTime,withVolume,repeat)
	{
		___kp_executeURL("kioskpro://kp_AudioPlayer_play?" + encodeURIComponent(filePath) + "&" + encodeURIComponent(atTime) + "&" + encodeURIComponent(withVolume) + "&" + encodeURIComponent(repeat));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AudioPlayer_play'] = function(filePath,atTime,withVolume,repeat) { kp_AudioPlayer_play(filePath,atTime,withVolume,repeat); };
}

if (typeof(kp_AudioPlayer_stop) !== "function")
{
	function kp_AudioPlayer_stop()
	{
		___kp_executeURL("kioskpro://kp_AudioPlayer_stop");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AudioPlayer_stop'] = function() { kp_AudioPlayer_stop(); };
}

if (typeof(kp_AudioPlayer_pause) !== "function")
{
	function kp_AudioPlayer_pause()
	{
		___kp_executeURL("kioskpro://kp_AudioPlayer_pause");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AudioPlayer_pause'] = function() { kp_AudioPlayer_pause(); };
}

if (typeof(kp_AudioPlayer_resume) !== "function")
{
	function kp_AudioPlayer_resume()
	{
		___kp_executeURL("kioskpro://kp_AudioPlayer_resume");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AudioPlayer_resume'] = function() { kp_AudioPlayer_resume(); };
}

if (typeof(kp_AudioPlayer_changeVolume) !== "function")
{
	function kp_AudioPlayer_changeVolume(volume)
	{
		___kp_executeURL("kioskpro://kp_AudioPlayer_changeVolume?" + encodeURIComponent(volume));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AudioPlayer_changeVolume'] = function(volume) { kp_AudioPlayer_changeVolume(volume); };
}

if (typeof(kp_AudioPlayer_changeCurrentTime) !== "function")
{
	function kp_AudioPlayer_changeCurrentTime(currentTime)
	{
		___kp_executeURL("kioskpro://kp_AudioPlayer_changeCurrentTime?" + encodeURIComponent(currentTime));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AudioPlayer_changeCurrentTime'] = function(currentTime) { kp_AudioPlayer_changeCurrentTime(currentTime); };
}

// AirPrinter API:
if (typeof(kp_AirPrinter_requestStateOfSupporting) !== "function")
{
	function kp_AirPrinter_requestStateOfSupporting()
	{
		___kp_executeURL("kioskpro://kp_AirPrinter_requestStateOfSupporting");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AirPrinter_requestStateOfSupporting'] = function() { kp_AirPrinter_requestStateOfSupporting(); };
}

if (typeof(kp_AirPrinter_print) !== "function")
{
	function kp_AirPrinter_print()
	{
		___kp_executeURL("kioskpro://kp_AirPrinter_print");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AirPrinter_print'] = function() { kp_AirPrinter_print(); };
}

if (typeof(kp_AirPrinter_printPdf) !== "function")
{
	function kp_AirPrinter_printPdf(filename)
	{
		___kp_executeURL("kioskpro://kp_AirPrinter_printPdf?" + encodeURIComponent(filename));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_AirPrinter_printPdf'] = function(filename) { kp_AirPrinter_printPdf(filename); };
}

// Custom America Printer API:
if (typeof(kp_CustomAmericaPrinterAPI_getPageWidth) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getPageWidth(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getPageWidth?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getPageWidth'] = function(callback) { kp_CustomAmericaPrinterAPI_getPageWidth(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontCharWidth) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontCharWidth(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontCharWidth?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontCharWidth'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontCharWidth(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontCharWidth) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontCharWidth(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontCharWidth?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontCharWidth'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontCharWidth(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontCharHeight) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontCharHeight(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontCharHeight?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontCharHeight'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontCharHeight(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontCharHeight) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontCharHeight(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontCharHeight?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontCharHeight'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontCharHeight(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontEmphasizedProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontEmphasizedProperty(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontEmphasizedProperty?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontEmphasizedProperty'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontEmphasizedProperty(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontEmphasizedProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontEmphasizedProperty(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontEmphasizedProperty?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontEmphasizedProperty'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontEmphasizedProperty(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontItalicProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontItalicProperty(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontItalicProperty?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontItalicProperty'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontItalicProperty(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontItalicProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontItalicProperty(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontItalicProperty?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontItalicProperty'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontItalicProperty(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontUnderlineProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontUnderlineProperty(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontUnderlineProperty?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontUnderlineProperty'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontUnderlineProperty(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontUnderlineProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontUnderlineProperty(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontUnderlineProperty?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontUnderlineProperty'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontUnderlineProperty(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontJustificationProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontJustificationProperty(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontJustificationProperty?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontJustificationProperty'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontJustificationProperty(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontJustificationProperty) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontJustificationProperty(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontJustificationProperty?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontJustificationProperty'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontJustificationProperty(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getCharFontType) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getCharFontType(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getCharFontType?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getCharFontType'] = function(callback) { kp_CustomAmericaPrinterAPI_getCharFontType(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setCharFontType) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setCharFontType(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setCharFontType?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setCharFontType'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setCharFontType(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_getFontInternationalCharSetType) !== "function")
{
	function kp_CustomAmericaPrinterAPI_getFontInternationalCharSetType(callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_getFontInternationalCharSetType?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_getFontInternationalCharSetType'] = function(callback) { kp_CustomAmericaPrinterAPI_getFontInternationalCharSetType(callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_setFontInternationalCharSetType) !== "function")
{
	function kp_CustomAmericaPrinterAPI_setFontInternationalCharSetType(value,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_setFontInternationalCharSetType?" + encodeURIComponent(value) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_setFontInternationalCharSetType'] = function(value,callback) { kp_CustomAmericaPrinterAPI_setFontInternationalCharSetType(value,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_printText) !== "function")
{
	function kp_CustomAmericaPrinterAPI_printText(text,pixel_la,pixel_w,feed,wordWrap,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_printText?" + encodeURIComponent(text) + "&" + encodeURIComponent(pixel_la) + "&" + encodeURIComponent(pixel_w) + "&" + encodeURIComponent(feed) + "&" + encodeURIComponent(wordWrap) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_printText'] = function(text,pixel_la,pixel_w,feed,wordWrap,callback) { kp_CustomAmericaPrinterAPI_printText(text,pixel_la,pixel_w,feed,wordWrap,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_printHTMLElement) !== "function")
{
	function kp_CustomAmericaPrinterAPI_printHTMLElement(elementId,wordWrap,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_printHTMLElement?" + encodeURIComponent(elementId) + "&" + encodeURIComponent(wordWrap) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_printHTMLElement'] = function(elementId,wordWrap,callback) { kp_CustomAmericaPrinterAPI_printHTMLElement(elementId,wordWrap,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_print2DBarCode) !== "function")
{
	function kp_CustomAmericaPrinterAPI_print2DBarCode(text,type,justification,width,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_print2DBarCode?" + encodeURIComponent(text) + "&" + encodeURIComponent(type) + "&" + encodeURIComponent(justification) + "&" + encodeURIComponent(width) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_print2DBarCode'] = function(text,type,justification,width,callback) { kp_CustomAmericaPrinterAPI_print2DBarCode(text,type,justification,width,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_printBarCode) !== "function")
{
	function kp_CustomAmericaPrinterAPI_printBarCode(text,type,hriType,justification,width,height,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_printBarCode?" + encodeURIComponent(text) + "&" + encodeURIComponent(type) + "&" + encodeURIComponent(hriType) + "&" + encodeURIComponent(justification) + "&" + encodeURIComponent(width) + "&" + encodeURIComponent(height) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_printBarCode'] = function(text,type,hriType,justification,width,height,callback) { kp_CustomAmericaPrinterAPI_printBarCode(text,type,hriType,justification,width,height,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_printImage) !== "function")
{
	function kp_CustomAmericaPrinterAPI_printImage(path,leftAlign,scaleOption,width,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_printImage?" + encodeURIComponent(path) + "&" + encodeURIComponent(leftAlign) + "&" + encodeURIComponent(scaleOption) + "&" + encodeURIComponent(width) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_printImage'] = function(path,leftAlign,scaleOption,width,callback) { kp_CustomAmericaPrinterAPI_printImage(path,leftAlign,scaleOption,width,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_feed) !== "function")
{
	function kp_CustomAmericaPrinterAPI_feed(numberOfLFToSend,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_feed?" + encodeURIComponent(numberOfLFToSend) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_feed'] = function(numberOfLFToSend,callback) { kp_CustomAmericaPrinterAPI_feed(numberOfLFToSend,callback); };
}

if (typeof(kp_CustomAmericaPrinterAPI_cut) !== "function")
{
	function kp_CustomAmericaPrinterAPI_cut(cutType,callback)
	{
		___kp_executeURL("kioskpro://kp_CustomAmericaPrinterAPI_cut?" + encodeURIComponent(cutType) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_CustomAmericaPrinterAPI_cut'] = function(cutType,callback) { kp_CustomAmericaPrinterAPI_cut(cutType,callback); };
}

// UniMag2 Card Reader API:
if (typeof(kp_UniMag2CardReader_requestStateOfSupporting) !== "function")
{
	function kp_UniMag2CardReader_requestStateOfSupporting()
	{
		___kp_executeURL("kioskpro://kp_UniMag2CardReader_requestStateOfSupporting");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_UniMag2CardReader_requestStateOfSupporting'] = function() { kp_UniMag2CardReader_requestStateOfSupporting(); };
}

if (typeof(kp_UniMag2CardReader_requestStateOfConnection) !== "function")
{
	function kp_UniMag2CardReader_requestStateOfConnection()
	{
		___kp_executeURL("kioskpro://kp_UniMag2CardReader_requestStateOfConnection");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_UniMag2CardReader_requestStateOfConnection'] = function() { kp_UniMag2CardReader_requestStateOfConnection(); };
}

if (typeof(kp_UniMag2CardReader_requestSwipe) !== "function")
{
	function kp_UniMag2CardReader_requestSwipe(swipeInfo)
	{
		___kp_executeURL("kioskpro://kp_UniMag2CardReader_requestSwipe?" + encodeURIComponent(swipeInfo));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_UniMag2CardReader_requestSwipe'] = function(swipeInfo) { kp_UniMag2CardReader_requestSwipe(swipeInfo); };
}

if (typeof(kp_UniMag2CardReader_cancelSwipe) !== "function")
{
	function kp_UniMag2CardReader_cancelSwipe()
	{
		___kp_executeURL("kioskpro://kp_UniMag2CardReader_cancelSwipe");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_UniMag2CardReader_cancelSwipe'] = function() { kp_UniMag2CardReader_cancelSwipe(); };
}

if (typeof(kp_UniMag2CardReader_mps_doCreditSaleOperation) !== "function")
{
	function kp_UniMag2CardReader_mps_doCreditSaleOperation(amount,invoiceNumber)
	{
		___kp_executeURL("kioskpro://kp_UniMag2CardReader_mps_doCreditSaleOperation?" + encodeURIComponent(amount) + "&" + encodeURIComponent(invoiceNumber));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_UniMag2CardReader_mps_doCreditSaleOperation'] = function(amount,invoiceNumber) { kp_UniMag2CardReader_mps_doCreditSaleOperation(amount,invoiceNumber); };
}

// StarPrinter API:
if (typeof(kp_StarPrinter_requestStateOfSupporting) !== "function")
{
	function kp_StarPrinter_requestStateOfSupporting()
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_requestStateOfSupporting");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_requestStateOfSupporting'] = function() { kp_StarPrinter_requestStateOfSupporting(); };
}

if (typeof(kp_StarPrinter_requestStatusOfPrinter) !== "function")
{
	function kp_StarPrinter_requestStatusOfPrinter()
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_requestStatusOfPrinter");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_requestStatusOfPrinter'] = function() { kp_StarPrinter_requestStatusOfPrinter(); };
}

if (typeof(kp_StarPrinter_selectCodePage) !== "function")
{
	function kp_StarPrinter_selectCodePage(codePage)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_selectCodePage?" + encodeURIComponent(codePage));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_selectCodePage'] = function(codePage) { kp_StarPrinter_selectCodePage(codePage); };
}

if (typeof(kp_StarPrinter_printText) !== "function")
{
	function kp_StarPrinter_printText(text,cut)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_printText?" + encodeURIComponent(text) + "&" + encodeURIComponent(cut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_printText'] = function(text,cut) { kp_StarPrinter_printText(text,cut); };
}

if (typeof(kp_StarPrinter_printHtml) !== "function")
{
	function kp_StarPrinter_printHtml(elementId,cut)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_printHtml?" + encodeURIComponent(elementId) + "&" + encodeURIComponent(cut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_printHtml'] = function(elementId,cut) { kp_StarPrinter_printHtml(elementId,cut); };
}

if (typeof(kp_StarPrinter_printCode39) !== "function")
{
	function kp_StarPrinter_printCode39(text,cut)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_printCode39?" + encodeURIComponent(text) + "&" + encodeURIComponent(cut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_printCode39'] = function(text,cut) { kp_StarPrinter_printCode39(text,cut); };
}

if (typeof(kp_StarPrinter_printCode93) !== "function")
{
	function kp_StarPrinter_printCode93(text,cut)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_printCode93?" + encodeURIComponent(text) + "&" + encodeURIComponent(cut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_printCode93'] = function(text,cut) { kp_StarPrinter_printCode93(text,cut); };
}

if (typeof(kp_StarPrinter_printCode128) !== "function")
{
	function kp_StarPrinter_printCode128(text,cut)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_printCode128?" + encodeURIComponent(text) + "&" + encodeURIComponent(cut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_printCode128'] = function(text,cut) { kp_StarPrinter_printCode128(text,cut); };
}

if (typeof(kp_StarPrinter_printQRCode) !== "function")
{
	function kp_StarPrinter_printQRCode(text,cut)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_printQRCode?" + encodeURIComponent(text) + "&" + encodeURIComponent(cut));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_printQRCode'] = function(text,cut) { kp_StarPrinter_printQRCode(text,cut); };
}

if (typeof(kp_StarPrinter_openCashDrawer) !== "function")
{
	function kp_StarPrinter_openCashDrawer(numberOfDrawer)
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_openCashDrawer?" + encodeURIComponent(numberOfDrawer));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_openCashDrawer'] = function(numberOfDrawer) { kp_StarPrinter_openCashDrawer(numberOfDrawer); };
}

if (typeof(kp_StarPrinter_requestCashDrawerStatus) !== "function")
{
	function kp_StarPrinter_requestCashDrawerStatus()
	{
		___kp_executeURL("kioskpro://kp_StarPrinter_requestCashDrawerStatus");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_StarPrinter_requestCashDrawerStatus'] = function() { kp_StarPrinter_requestCashDrawerStatus(); };
}

// Common Printer API:
if (typeof(print) !== "function")
{
	function print()
	{
		___kp_executeURL("kioskpro://print");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['print'] = function() { print(); };
}

// Idle Timer API:
if (typeof(kp_IdleTimer_fire) !== "function")
{
	function kp_IdleTimer_fire()
	{
		___kp_executeURL("kioskpro://kp_IdleTimer_fire");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_IdleTimer_fire'] = function() { kp_IdleTimer_fire(); };
}

// KioWare API:
if (typeof(kp_KioWare_closeCurrentSession) !== "function")
{
	function kp_KioWare_closeCurrentSession()
	{
		___kp_executeURL("kioskpro://kp_KioWare_closeCurrentSession");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_KioWare_closeCurrentSession'] = function() { kp_KioWare_closeCurrentSession(); };
}

if (typeof(kp_KioWare_registerNavigation) !== "function")
{
	function kp_KioWare_registerNavigation(url,pageTitle,callback)
	{
		___kp_executeURL("kioskpro://kp_KioWare_registerNavigation?" + encodeURIComponent(url) + "&" + encodeURIComponent(pageTitle) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_KioWare_registerNavigation'] = function(url,pageTitle,callback) { kp_KioWare_registerNavigation(url,pageTitle,callback); };
}

// Device Link Server API:
if (typeof(kp_DeviceLinkServer_start) !== "function")
{
	function kp_DeviceLinkServer_start(serverName,callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkServer_start?" + encodeURIComponent(serverName) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkServer_start'] = function(serverName,callback) { kp_DeviceLinkServer_start(serverName,callback); };
}

if (typeof(kp_DeviceLinkServer_stop) !== "function")
{
	function kp_DeviceLinkServer_stop(serverName,callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkServer_stop?" + encodeURIComponent(serverName) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkServer_stop'] = function(serverName,callback) { kp_DeviceLinkServer_stop(serverName,callback); };
}

if (typeof(kp_DeviceLinkServer_getState) !== "function")
{
	function kp_DeviceLinkServer_getState(serverName,callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkServer_getState?" + encodeURIComponent(serverName) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkServer_getState'] = function(serverName,callback) { kp_DeviceLinkServer_getState(serverName,callback); };
}

// Device Link Connection API:
if (typeof(kp_DeviceLinkConnection_connectToServer) !== "function")
{
	function kp_DeviceLinkConnection_connectToServer(serverName,connectionName,callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkConnection_connectToServer?" + encodeURIComponent(serverName) + "&" + encodeURIComponent(connectionName) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkConnection_connectToServer'] = function(serverName,connectionName,callback) { kp_DeviceLinkConnection_connectToServer(serverName,connectionName,callback); };
}

if (typeof(kp_DeviceLinkConnection_close) !== "function")
{
	function kp_DeviceLinkConnection_close(serverName,callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkConnection_close?" + encodeURIComponent(serverName) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkConnection_close'] = function(serverName,callback) { kp_DeviceLinkConnection_close(serverName,callback); };
}

if (typeof(kp_DeviceLinkConnection_sendPacketToServer) !== "function")
{
	function kp_DeviceLinkConnection_sendPacketToServer(serverName,packet,callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkConnection_sendPacketToServer?" + encodeURIComponent(serverName) + "&" + encodeURIComponent(packet) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkConnection_sendPacketToServer'] = function(serverName,packet,callback) { kp_DeviceLinkConnection_sendPacketToServer(serverName,packet,callback); };
}

if (typeof(kp_DeviceLinkConnection_getListOfAliveConnections) !== "function")
{
	function kp_DeviceLinkConnection_getListOfAliveConnections(callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkConnection_getListOfAliveConnections?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkConnection_getListOfAliveConnections'] = function(callback) { kp_DeviceLinkConnection_getListOfAliveConnections(callback); };
}

// Device Link Browser API:
if (typeof(kp_DeviceLinkBrowser_start) !== "function")
{
	function kp_DeviceLinkBrowser_start(callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkBrowser_start?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkBrowser_start'] = function(callback) { kp_DeviceLinkBrowser_start(callback); };
}

if (typeof(kp_DeviceLinkBrowser_stop) !== "function")
{
	function kp_DeviceLinkBrowser_stop()
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkBrowser_stop");
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkBrowser_stop'] = function() { kp_DeviceLinkBrowser_stop(); };
}

if (typeof(kp_DeviceLinkBrowser_getListOfServers) !== "function")
{
	function kp_DeviceLinkBrowser_getListOfServers(callback)
	{
		___kp_executeURL("kioskpro://kp_DeviceLinkBrowser_getListOfServers?" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_DeviceLinkBrowser_getListOfServers'] = function(callback) { kp_DeviceLinkBrowser_getListOfServers(callback); };
}

// Zapier API:
if (typeof(kp_Zapier_sendNotificationToZap) !== "function")
{
	function kp_Zapier_sendNotificationToZap(urlOfZap,data,callback)
	{
		___kp_executeURL("kioskpro://kp_Zapier_sendNotificationToZap?" + encodeURIComponent(urlOfZap) + "&" + encodeURIComponent(data) + "&" + encodeURIComponent(callback));
	}
}

for (_kp_i_ = 0; _kp_i_ < _kp_frames_special_.length; ++_kp_i_)
{
	_kp_frames_special_[_kp_i_].contentWindow['kp_Zapier_sendNotificationToZap'] = function(urlOfZap,data,callback) { kp_Zapier_sendNotificationToZap(urlOfZap,data,callback); };
}


// Set hooks are available:
window.kioskpro_hooks_available = 1;