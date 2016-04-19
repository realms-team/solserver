var map;
var markers = [];

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: {lat: -33.114274, lng: -68.480041},
        zoom: 19
    });
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE);
}

function load_data(){
    query       = "SELECT * FROM SOL_TYPE_DUST_OAP_TEMPSAMPLE LIMIT 1";
    enc_query   = encodeURIComponent(query);
    $.getJSON("jsonp/" + enc_query, create_paths);
    //setTimeout(load_data(), 1000000);
}

function create_paths(data){
    console.log(data)
    for (var i=0; i < data.length; i++) {
        var myLatLng = new google.maps.LatLng(
                                data[i].value.latitude,
                                data[i].value.longitude);
        if (markerExists(myLatLng)==0){
            var marker = new google.maps.Marker({
                position: myLatLng,
                map: map,
            });
            markers.push(marker);
        }
    }
}

function markerExists(LatLng){
    for( i=0; i<markers.length; i++ ) {
        if (markers[i].getPosition().toString() == LatLng.toString())
          return 1;
    }
    return 0;
}
