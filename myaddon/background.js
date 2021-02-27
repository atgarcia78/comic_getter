var blocking = true;

function toggleListener() {
 
  blocking = !blocking;
}

function redirect(requestDetails) {
	if(blocking){
			  return {
		redirectUrl: requestDetails.url
	  };
	}
	else
	{
	  return {
		redirectUrl: null
	  };
	}
}

browser.webRequest.onBeforeRequest.addListener(
  redirect,
  {urls:["<all_urls>"], types:["image", "imageset"]},
  ["blocking"]
);

browser.browserAction.onClicked.addListener(toggleListener);