from django.urls import path
from human_resource.views import *

urlpatterns = [

    path('department/create', DepartmentCreateView.as_view(), name='department_create'),
    path('department/index', DepartmentListView.as_view(), name='department_index'),
    path('department/<int:pk>/detail', DepartmentDetailView.as_view(), name='department_detail'),
    path('department/<int:pk>/edit', DepartmentUpdateView.as_view(), name='department_edit'),
    path('department/<int:pk>/delete', DepartmentDeleteView.as_view(), name='department_delete'),
    path('department/multi-action', multi_department_action, name='multi_department_action'),
    path('department/<int:pk>/assign-hod/', assign_hod, name='assign_hod'),

    path('position/create', PositionCreateView.as_view(), name='position_create'),
    path('position/index', PositionListView.as_view(), name='position_index'),
    path('position/<int:pk>/edit', PositionUpdateView.as_view(), name='position_edit'),
    path('position/<int:pk>/delete', PositionDeleteView.as_view(), name='position_delete'),

    path('staff/create', StaffCreateView.as_view(), name='staff_create'),
    path('staff/index', StaffListView.as_view(), name='staff_index'),
    path('staff/<int:pk>/detail', StaffDetailView.as_view(), name='staff_detail'),
    path('staff/<int:pk>/edit', StaffUpdateView.as_view(), name='staff_edit'),
    path('staff/<int:pk>/delete', StaffDeleteView.as_view(), name='staff_delete'),
    path('staff/<int:pk>/finger-print-capture', StaffFingerPrintCaptureView.as_view(), name='staff_finger_print_capture'),
    path('staff/<int:staff_id>/disable/', disable_staff, name='disable_staff'),
    path('staff/<int:staff_id>/enable/', enable_staff, name='enable_staff'),
    path('staff/<int:staff_id>/generate-login/', generate_staff_login, name='generate_staff_login'),
    path('staff/<int:staff_id>/update-login/', update_staff_login, name='update_staff_login'),

    path('setting/create', HRSettingCreateView.as_view(), name='human_resource_setting_create'),
    path('setting/<int:pk>/detail', HRSettingDetailView.as_view(), name='human_resource_setting_detail'),
    path('setting/<int:pk>/edit', HRSettingUpdateView.as_view(), name='human_resource_setting_edit'),

    path('group/add', GroupCreateView.as_view(), name='group_create'),
    path('group/index', GroupListView.as_view(), name='group_index'),
    path('group/<int:pk>/detail', GroupDetailView.as_view(), name='group_detail'),
    path('group/<int:pk>/edit', GroupUpdateView.as_view(), name='group_edit'),
    path('group/<int:pk>/permission/edit', group_permission_view, name='group_permission'),
    path('group/<int:pk>/delete', GroupDeleteView.as_view(), name='group_delete'),

    path('staff/document/add/', StaffDocumentCreateView.as_view(), name='staff_document_add'),
    path('staff/document/<int:pk>/edit/', StaffDocumentUpdateView.as_view(), name='staff_document_edit'),
    path('staff/document/<int:pk>/delete/', StaffDocumentDeleteView.as_view(), name='staff_document_delete'),

    path('leave/apply/', StaffLeaveCreateView.as_view(), name='leave_apply'),
    path('leave/<int:pk>/edit/', StaffLeaveUpdateView.as_view(), name='leave_edit'),
    path('leave/my/', StaffLeaveListView.as_view(), name='my_leaves'),
    path('leave/pending/', LeaveApprovalListView.as_view(), name='leave_approval_list'),
    path('leave/all/', AllLeaveListView.as_view(), name='all_leaves'),
    path('leave/<int:pk>/approve/', approve_leave, name='leave_approve'),
    path('leave/<int:pk>/decline/', decline_leave, name='leave_decline'),



]

