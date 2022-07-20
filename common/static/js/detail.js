$(document).ready( function() {
    
    $(".modal-close").on('click', function() {
        $(this).parents(".modal").hide();
        $(".bg-mask").hide();
    });

    // pop up new rating modal
    $("#addMarkPanel button").each(function() {
        $(this).on('click', function(e) {
            e.preventDefault();
            let title = $(this).text().trim();
            $(".mark-modal__title").text(title);
            $(".mark-modal__body textarea").val("");
            let status = $(this).data('status')
            $("input[name='status'][value='"+status+"']").prop("checked", true)
            $(".bg-mask").show();
            $(".mark-modal").show();

            // if wish, hide rating widget in modal
            if ($(this).attr("id") == "wishButton") {
                // console.log($(this).attr("id"))
                $(".mark-modal .rating-star-edit").hide();
            } else {
                $(".mark-modal .rating-star-edit").show();
            }

        });
    })

    // pop up modify mark modal
    $(".mark-panel a.edit").on('click', function(e) {
        e.preventDefault();
        let title = $(".mark-panel__status").text().trim();
        $(".mark-modal__title").text(title);
        $(".bg-mask").show();
        $(".mark-modal").show();
    });

    // readonly star rating of detail display section
    let ratingLabels = $("#main .rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true,
        });
    });
    // readonly star rating at aside section
    ratingLabels = $("#aside .rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true,
            starSize: 15,
        });
    });

    // editable rating star in modal
    ratingLabels = $("#modals .rating-star-edit");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $("input[type='hidden'][name='rating']").val() / 2;
        let label = $(this);
        label.starRating({
            initialRating: ratingScore,
            starSize: 20,
            onHover: function(currentIndex, currentRating, $el){
                $("input[type='hidden'][name='rating']").val(currentIndex);
            },
            onLeave: function(currentIndex, currentRating, $el){
                $("input[type='hidden'][name='rating']").val(currentRating * 2);
            }            
        });
    });
    
    // hide rating star when select wish
    const WISH_CODE = "wish";
    if ($("#statusSelection input[type='radio']:checked").val() == WISH_CODE) {
        $(".mark-modal .rating-star-edit").hide();
    }
    $("#statusSelection input[type='radio']").on('click', function() {
        if ($(this).val() == WISH_CODE) {
            $(".mark-modal .rating-star-edit").hide();
        } else {
            $(".mark-modal .rating-star-edit").show();
        }
        
    });

    // show confirm modal
    $(".mark-panel a.delete").on('click', function(e) {
        e.preventDefault();
        $(".confirm-modal").show();
        $(".bg-mask").show();
    });

    // confirm modal
    $(".confirm-modal input[type='submit']").on('click', function(e) {
        e.preventDefault();
        $(".mark-panel form").submit();
    });
    

    // hide long text
    $(".entity-desc__content").each(function() {
        let copy = $(this).clone()
            .addClass('entity-desc__content--folded')
            .css("visibility", "hidden");
        $(this).after(copy);
        if ($(this).height() > copy.height()) {
            $(this).addClass('entity-desc__content--folded');
            $(this).siblings(".entity-desc__unfold-button").removeClass("entity-desc__unfold-button--hidden");
        }
        copy.remove();        
    });

    // expand hidden long text
    $(".entity-desc__unfold-button a").on('click', function() {
        $(this).parent().siblings(".entity-desc__content").removeClass('entity-desc__content--folded');
        $(this).parent(".entity-desc__unfold-button").remove();
    });
    
    // disable delete mark button after click
    const confirmDeleteMarkButton = $('.confirm-modal__confirm-button > input');
    confirmDeleteMarkButton.on('click', function() {
        confirmDeleteMarkButton.prop("disabled", true);
    });

    // disable sumbit button after click
    const confirmSumbitMarkButton = $('.mark-modal__confirm-button > input');
    confirmSumbitMarkButton.on('click', function() {
        confirmSumbitMarkButton.prop("disabled", true);
        confirmSumbitMarkButton.closest('form')[0].submit();
    });

});