<?php
/* Plugin Name: Elite Basketball Manager
Description: Basketball coaching demo with automatic game page.
Version: 0.2.0
*/
if (!defined('ABSPATH')) exit;
function ebm_ensure_page(){
$id=(int)get_option('ebm_play_page_id');
if($id && get_post_type($id)==='page' && get_post_status($id)!=='trash')return;
$p=get_posts(array('post_type'=>'page','post_status'=>array('publish','draft','private'),'meta_key'=>'_ebm_generated','meta_value'=>'1','numberposts'=>1));
if($p){update_option('ebm_play_page_id',$p[0]->ID);return;}
$id=wp_insert_post(array('post_type'=>'page','post_status'=>'publish','post_title'=>'Παίξε — Elite Basketball Manager','post_content'=>'[elite_basketball_manager]','meta_input'=>array('_ebm_generated'=>'1')),true);
if(!is_wp_error($id))update_option('ebm_play_page_id',$id);
}
register_activation_hook(__FILE__,'ebm_ensure_page');
add_action('admin_init',function(){if(current_user_can('manage_options') && get_option('ebm_demo_version')!=='0.2.0'){ebm_ensure_page();update_option('ebm_demo_version','0.2.0');}});
add_shortcode('elite_basketball_manager',function(){return '<iframe allow="fullscreen" title="Elite Basketball Manager" src="'.esc_url(plugins_url('game.html',__FILE__).'?v=0.2.0').'" style="width:100%;height:1100px;border:0;background:#080e1b"></iframe>';});
add_action('admin_menu',function(){add_menu_page('Elite Basketball','Elite Basketball','manage_options','ebm-demo',function(){if(!current_user_can('manage_options'))return;$id=(int)get_option('ebm_play_page_id');echo '<div class="wrap"><h1>Elite Basketball Manager 0.2.0</h1>';if($id && get_post_status($id)==='publish')echo '<a class="button button-primary" target="_blank" rel="noopener" href="'.esc_url(get_permalink($id)).'">Άνοιγμα παιχνιδιού</a>';echo '</div>';},'dashicons-games');});
