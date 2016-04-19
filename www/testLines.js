function initialize() {
        var latitude = -33.11435, //TODO automatic centering according the points
            longitude = -68.47997, //TODO automatic centering according the points
            radius = 8000, //how is this set up
            center = new google.maps.LatLng(latitude,longitude),
            bounds = new google.maps.Circle({center: center, radius: radius}).getBounds(),
            mapOptions = {
                center: center,
                zoom: 20,
                mapTypeId: google.maps.MapTypeId.SATELLITE,
                scrollwheel: false
            };

        var map = new google.maps.Map(document.getElementById("map-canvas"), mapOptions);

        setMarkers(center, radius, map);
	setPaths(map);
    }

/*CALL THE DATABASE INSIDE THIS FUNCTION*/
    function getData(){

	//returns json test file
/*
58-32-36
latitude
-33.11464
longitude
-68.48015

60-03-82
latitude
-33.11469
longitude
-68.48005

60-08-D5
latitude
-33.11444
longitude
-68.48024

60-06-0F
latitude
-33.1145
longitude
-68.48016

{"lat":,"lng":,"content":}
*/
	return [

		{"lat":-33.11454,"lng":-68.47996,"label":"1","content":"3F-F3-87 <BR> newlineInfoHere!"},
		{"lat":-33.11446,"lng":-68.48001,"label":"2","content":"3F-FE-88"},
		{"lat":-33.11464,"lng":-68.48028,"label":"3","content":"3F-F8-20"},
		{"lat":-33.11456,"lng":-68.48035,"label":"4","content":"30-60-EF"},
		{"lat":-33.11428,"lng":-68.48012,"label":"6","content":"60-05-5F"},
		{"lat": -33.11435, "lng": -68.47997,"label":"7", "content":"other values"}, 
		{"lat": -33.11407,"lng": -68.47978,"label":"8","content":"test content3"},
		{"lat":-33.11469,"lng":-68.48005,"label":"9","content":"60-03-82"}
	];
	}

function getPaths()
{
	return [

		{"sourcelat":-33.11454,"sourcelng":-68.47996,"destlat":-33.11446,"destlng":-68.48001,"color":'#ff0000'}, //test red
		{"sourcelat":-33.11464,"sourcelng":-68.48028,"destlat":-33.11428,"destlng":-68.48012,"color":'#ffff00'}, //test yellow
		{"sourcelat":-33.11407,"sourcelng":-68.47978,"destlat":-33.11469,"destlng":-68.48005,"color":'#00ff00'} //test green
	];
}

function createLine(lineCoordinates,color,map){
  var tripPath = new google.maps.Polyline({
    path: lineCoordinates,
    geodesic: true,
    strokeColor: color,
    strokeOpacity: 1.0,
    strokeWeight: 2
  });
  tripPath.setMap(map);
}


function setPaths(map)
{
	var json = getPaths();
	for (var i = 0, length = json.length; i < length; i++) {
            var data = json[i];
            var lineCoordinates = [
	     new google.maps.LatLng(data.sourcelat,data.sourcelng),
	     new google.maps.LatLng(data.destlat,data.destlng)
	    ];
	    createLine(lineCoordinates,data.color,map);
        }
}
/*Draws each sensor on the map*/
    function setMarkers(center, radius, map) {

    var json = getData();

    var circle = new google.maps.Circle({
                strokeColor: '#000000',
                strokeOpacity: 0.25,
                strokeWeight: 1.0,
                fillColor: '#ffffff',
                fillOpacity: 0.1,
                clickable: false,
                map: map,
                center: center,
                radius: radius
            });
        var bounds = circle.getBounds();

        //loop between each of the json elements
        for (var i = 0, length = json.length; i < length; i++) {
            var data = json[i],
            latLng = new google.maps.LatLng(data.lat, data.lng);

            if(bounds.contains(latLng)) {
                // Creating a marker and putting it on the map
                var marker = new google.maps.Marker({
                    position: latLng,
                    map: map,
                    title: data.content,
		    label: data.label
                });
                infoBox(map, marker, data);
            }
        }

        circle.bindTo('center', marker, 'position');
    }

/*Function that shows a window with the content or info
 about the marker (sensor location)*/

    function infoBox(map, marker, data) {
        var infoWindow = new google.maps.InfoWindow();
        // Attaching a click event to the current marker
        google.maps.event.addListener(marker, "click", function(e) {
            infoWindow.setContent(data.content);
            infoWindow.open(map, marker);
        });

        // Creating a closure to retain the correct data 
        // Note how I pass the current data in the loop into the closure (marker, data)
        (function(marker, data) {
          // Attaching a click event to the current marker
          google.maps.event.addListener(marker, "click", function(e) {
            infoWindow.setContent(data.content);
            infoWindow.open(map, marker);
          });
        })(marker, data);
    }

   google.maps.event.addDomListener(window, 'load', initialize);
