from oscar.apps.promotions.views import HomeView as CoreHomeView


class HomeView(CoreHomeView):
    template_name = 'promotions/new_home.html'
