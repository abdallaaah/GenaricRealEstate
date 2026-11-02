
    $(document).ready(function () {
        $('.lead-stage-button').click(function (e) {
            e.preventDefault();
            var $btn = $(this);
            var leadId = $btn.data('lead-id');
            var stageId = $btn.data('stage-id');

            $.ajax({
                url: '/my/lead/update_stage',
                type: 'POST',
                data: {
                    lead_id: leadId,
                    stage_id: stageId,
                },
                dataType: 'json',
                success: function (data) {
                    console.log(data);
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert(data.error || 'An error occurred');
                    }
                },
                error: function () {
                    alert('Failed to update stage');
                }
            });
        });
    });
