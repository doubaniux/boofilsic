function getUsers(since, limit){
    let token = $("#oauth2Token").text();
    let mast_uri = $("#mastodonURI").text();
    let id = $("#userMastodonID").text();
    if (since == null) {
        since = 0
    }
    let url = mast_uri + API_FOLLOWERS.replace(":id", id) + "?limit=" + limit + "&since_id=" + since;
    $.ajax({
        url: url,
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + token
        },
        success: function (userList) {
            if (userList.length == 0) {
                alert("no data")
            }
            let template = $(".user").clone();
            $(".user").html("");
            userList.forEach(data => {
                temp = $(template).clone()
                temp.find("img").attr("src", data.avatar);
                if (data.display_name) {
                    temp.find("a").text(data.display_name);
                } else {
                    temp.find("a").text(data.username);
                }
                $(".user").append(temp);
            });
        },
    });
}
