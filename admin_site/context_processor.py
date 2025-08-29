from admin_site.models import SiteInfoModel


def general_info(request):
    hospital_info = SiteInfoModel.objects.first()

    return {
        'site_info': hospital_info,
    }
