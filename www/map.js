var map;
var markers = [];
var motes = [];
var links = [];

//------------------ Init functions ------------------------------------------//

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: {lat: -33.114274, lng: -68.480041},
        zoom: 19
    });
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE);
}

function load_data(){
    clearLinks();

    // MOTE CREATE
    query = "SOL_TYPE_DUST_EVENTMOTECREATE";
    enc_query   = encodeURIComponent(query);
    $.getJSON("jsonp/" + enc_query, create_mote);

    // NEIGHBORS
    query = "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS";
    enc_query   = encodeURIComponent(query);
    $.getJSON("jsonp/" + enc_query, create_links);

    setTimeout(load_data, 30000);
}

//------------------ Main functions ------------------------------------------//

function create_mote(data){
    console.log(data.length)
    for (var i=0; i < data.length; i++) {
        // create Markers
        var myLatLng = new google.maps.LatLng(
                                data[i].value.latitude,
                                data[i].value.longitude);
        var marker = new google.maps.Marker({
            position: myLatLng,
            map: map,
        });
        infoBox(map, marker, data[i]);

        // populate table
        motes[data[i].value.moteId] = [data[i].mac, marker]
    }
}

function create_links(data){
    for (var i=0; i < data.length; i++) {
        for (var j=0; j<data[i].value.neighbors.length; j++){
            if (data[i].value.neighbors[j].neighborId in motes){
                var lineCoordinates = [
                    getLocationFromMac(data[i].mac),
                    getLocationFromId(data[i].value.neighbors[j].neighborId)
                ];
                color = getLinkColor(data[i].value.neighbors[j].rssi)
                createLine(lineCoordinates,color);
            }
        }
    }
}

//------------------ Helpers ------------------------------------------------//

function clearLinks(){
    // remove links
    console.log(links.length)
    for (i=0; i<links.length; i++) {
        if (i in links){
            links[i].setMap(null);
        }
    }
    links = []
}

function getLinkColor(rssi){
    console.log(rssi)
    if (rssi<-90)
        return "#ff0000"
    else if (rssi<-80 && rssi>-90)
        return "#ffff00"
    else
        return "#00ff00"
}

function createLine(lineCoordinates,color){
    var tripPath = new google.maps.Polyline({
          path: lineCoordinates,
          geodesic: true,
          strokeColor: color,
          strokeOpacity: 1.0,
          strokeWeight: 2
    });
    tripPath.setMap(map);
    links.push(tripPath);
}


function markerExists(LatLng){
    for (i=0; i<markers.length; i++ ) {
        if (markers[i].getPosition().toString() == LatLng.toString())
          return 1;
    }
    return 0;
}

function getLocationFromId(moteId){
    pos = motes[moteId][1].position;
    return new google.maps.LatLng(
        pos.lat(),
        pos.lng());
}

function getLocationFromMac(mac){
    for( i=0; i<motes.length; i++ ) {
        if (i in motes && motes[i][0] == mac){
            pos = motes[i][1].position;
            return new google.maps.LatLng(
                pos.lat(),
                pos.lng());
        }
    }
}

/*Function that shows a window with the content or info
 about the marker (sensor location)*/

function infoBox(map, marker, data) {
    var infoWindow = new google.maps.InfoWindow();
    // Attaching a click event to the current marker
    google.maps.event.addListener(marker, "click", function(e) {
        infoWindow.setContent(data.mac);
        infoWindow.open(map, marker);
    });
}

