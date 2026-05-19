<?php
/**
 * Plugin Name: Gridar Connector
 * Description: Connecte ce site WordPress a Gridar en 1 click, sans copier-coller d'Application Password.
 * Version: 1.0.0
 * Author: Arivex Studio
 * Author URI: https://gridar.app
 * License: MIT
 * Requires at least: 5.6
 * Requires PHP: 7.4
 *
 * Comment ca marche :
 *   1. L'utilisateur installe ce plugin sur son WP.
 *   2. Il va dans Reglages -> Gridar.
 *   3. Il colle son token API Gridar (genere sur gridar.app/account/api-keys, 1 fois).
 *   4. Click sur "Connecter" -> le plugin genere automatiquement une Application
 *      Password via la WP Application Passwords API, et l'envoie a Gridar avec
 *      le token. Gridar cree le Site dans le compte du user et renvoie le
 *      dashboard URL.
 *   5. L'utilisateur clique sur le lien -> il est dans son dashboard Gridar
 *      avec le site WP deja connecte.
 *
 * Aucune valeur sensible (mot de passe, App Password) n'est jamais affichee a
 * l'utilisateur. Tout passe en backend via wp_remote_post().
 */

if (!defined('ABSPATH')) {
    exit;
}

define('GRIDAR_CONNECTOR_VERSION', '1.0.0');
define('GRIDAR_CONNECTOR_API_BASE', 'https://api.gridar.app/api');
define('GRIDAR_CONNECTOR_OPTION_KEY', 'gridar_connector_state');


/**
 * Register the admin page under Settings -> Gridar.
 */
function gridar_connector_admin_menu() {
    add_options_page(
        'Gridar',
        'Gridar',
        'manage_options',
        'gridar-connector',
        'gridar_connector_render_page'
    );
}
add_action('admin_menu', 'gridar_connector_admin_menu');


/**
 * Render the admin page.
 */
function gridar_connector_render_page() {
    if (!current_user_can('manage_options')) {
        wp_die('Acces refuse.');
    }

    $state = get_option(GRIDAR_CONNECTOR_OPTION_KEY, array());
    $is_connected = !empty($state['site_id']);
    $error = '';
    $success = '';

    // Handle connect form submission.
    if (
        isset($_POST['gridar_action']) &&
        $_POST['gridar_action'] === 'connect' &&
        check_admin_referer('gridar_connect_action', 'gridar_nonce')
    ) {
        $token = isset($_POST['gridar_api_token']) ? trim(sanitize_text_field(wp_unslash($_POST['gridar_api_token']))) : '';
        $result = gridar_connector_do_connect($token);
        if (is_wp_error($result)) {
            $error = $result->get_error_message();
        } else {
            $success = 'Site connecte a Gridar.';
            $state = $result;
            $is_connected = true;
        }
    }

    // Handle disconnect.
    if (
        isset($_POST['gridar_action']) &&
        $_POST['gridar_action'] === 'disconnect' &&
        check_admin_referer('gridar_disconnect_action', 'gridar_nonce')
    ) {
        gridar_connector_do_disconnect();
        $state = array();
        $is_connected = false;
        $success = 'Deconnecte. (La cle d\'application Gridar a ete revoquee dans WordPress.)';
    }

    ?>
    <div class="wrap">
        <h1>Gridar - SEO + generation d'articles IA</h1>
        <p>Connecte ce site a Gridar en 1 click pour generer des articles SEO, faire des audits, suivre tes positions.</p>

        <?php if ($error) : ?>
            <div class="notice notice-error"><p><?php echo esc_html($error); ?></p></div>
        <?php endif; ?>
        <?php if ($success) : ?>
            <div class="notice notice-success"><p><?php echo esc_html($success); ?></p></div>
        <?php endif; ?>

        <?php if ($is_connected) : ?>
            <div class="card" style="max-width: 600px; padding: 20px; margin-top: 20px;">
                <h2 style="margin-top: 0;">Site connecte</h2>
                <p>
                    <strong>Nom :</strong> <?php echo esc_html($state['name'] ?? ''); ?><br>
                    <strong>Domaine :</strong> <?php echo esc_html($state['domain'] ?? ''); ?><br>
                    <strong>Site ID Gridar :</strong> <?php echo esc_html($state['site_id'] ?? ''); ?>
                </p>
                <p>
                    <a href="<?php echo esc_url($state['dashboard_url'] ?? 'https://gridar.app/sites'); ?>" target="_blank" class="button button-primary">
                        Ouvrir le dashboard Gridar
                    </a>
                </p>
                <form method="post" style="margin-top: 20px;">
                    <?php wp_nonce_field('gridar_disconnect_action', 'gridar_nonce'); ?>
                    <input type="hidden" name="gridar_action" value="disconnect">
                    <button type="submit" class="button">Deconnecter ce site</button>
                </form>
            </div>
        <?php else : ?>
            <div class="card" style="max-width: 600px; padding: 20px; margin-top: 20px;">
                <h2 style="margin-top: 0;">Connexion en 1 click</h2>
                <ol style="margin-left: 20px;">
                    <li>
                        Va sur <a href="https://gridar.app/account/api-keys" target="_blank">gridar.app/account/api-keys</a>
                        et genere un token.
                    </li>
                    <li>Colle-le ci-dessous.</li>
                    <li>Click "Connecter" - on s'occupe du reste.</li>
                </ol>
                <form method="post" style="margin-top: 20px;">
                    <?php wp_nonce_field('gridar_connect_action', 'gridar_nonce'); ?>
                    <input type="hidden" name="gridar_action" value="connect">
                    <label for="gridar_api_token"><strong>Token API Gridar :</strong></label><br>
                    <input
                        type="password"
                        id="gridar_api_token"
                        name="gridar_api_token"
                        class="regular-text"
                        autocomplete="off"
                        required
                        placeholder="btb_xxxxxxxxxxxxxxxxxxxxxxxx"
                        style="width: 100%; max-width: 500px;"
                    >
                    <p style="margin-top: 15px;">
                        <button type="submit" class="button button-primary">Connecter ce site a Gridar</button>
                    </p>
                </form>
                <p style="font-size: 12px; color: #666; margin-top: 20px;">
                    Le plugin va generer automatiquement une Application Password WordPress
                    et l'envoyer chiffree (HTTPS) a Gridar. Tu n'as aucun copier-coller a faire.
                    Tu peux revoquer la connexion a tout moment depuis cette page ou depuis
                    Utilisateurs -> Profil -> Application Passwords.
                </p>
            </div>
        <?php endif; ?>
    </div>
    <?php
}


/**
 * Generate an Application Password and send it to Gridar.
 * Returns either the Gridar state dict (saved to options) or a WP_Error.
 */
function gridar_connector_do_connect($token) {
    if (empty($token)) {
        return new WP_Error('missing_token', 'Le token Gridar est requis.');
    }
    if (!class_exists('WP_Application_Passwords')) {
        return new WP_Error(
            'wp_too_old',
            'WordPress 5.6+ requis pour les Application Passwords.'
        );
    }

    $user_id = get_current_user_id();
    if (!$user_id) {
        return new WP_Error('no_user', 'Pas d\'utilisateur courant.');
    }

    // Generate a fresh Application Password labeled so the user sees its
    // origin in Users -> Profile -> Application Passwords.
    $app_pass = WP_Application_Passwords::create_new_application_password(
        $user_id,
        array(
            'name'   => 'Gridar Connector',
            'app_id' => 'gridar-connector',
        )
    );
    if (is_wp_error($app_pass)) {
        return $app_pass;
    }
    list($plain_password, $details) = $app_pass;

    $current_user = wp_get_current_user();
    $payload = array(
        'wp_url'       => home_url(),
        'username'     => $current_user->user_login,
        'app_password' => $plain_password,
        'name'         => get_bloginfo('name'),
    );

    $response = wp_remote_post(
        GRIDAR_CONNECTOR_API_BASE . '/v1/wp-connector/connect/',
        array(
            'headers' => array(
                'Authorization' => 'Bearer ' . $token,
                'Content-Type'  => 'application/json',
            ),
            'body'    => wp_json_encode($payload),
            'timeout' => 30,
        )
    );

    if (is_wp_error($response)) {
        // Rollback the App Password since the connect failed.
        WP_Application_Passwords::delete_application_password($user_id, $details['uuid']);
        return new WP_Error(
            'http_error',
            'Erreur reseau vers Gridar : ' . $response->get_error_message()
        );
    }

    $code = wp_remote_retrieve_response_code($response);
    $body = json_decode(wp_remote_retrieve_body($response), true);

    if ($code >= 400 || empty($body['site_id'])) {
        WP_Application_Passwords::delete_application_password($user_id, $details['uuid']);
        $msg = isset($body['error']) ? $body['error'] : 'Reponse inattendue de Gridar';
        return new WP_Error('gridar_error', $msg);
    }

    $state = array(
        'site_id'       => intval($body['site_id']),
        'name'          => isset($body['name']) ? sanitize_text_field($body['name']) : '',
        'domain'        => isset($body['domain']) ? sanitize_text_field($body['domain']) : '',
        'dashboard_url' => isset($body['dashboard_url']) ? esc_url_raw($body['dashboard_url']) : '',
        'app_pass_uuid' => $details['uuid'],
        'connected_at'  => time(),
    );
    update_option(GRIDAR_CONNECTOR_OPTION_KEY, $state, false);

    return $state;
}


/**
 * Revoke the Application Password we created and clear local state.
 */
function gridar_connector_do_disconnect() {
    $state = get_option(GRIDAR_CONNECTOR_OPTION_KEY, array());
    $uuid = $state['app_pass_uuid'] ?? '';
    if ($uuid && class_exists('WP_Application_Passwords')) {
        WP_Application_Passwords::delete_application_password(get_current_user_id(), $uuid);
    }
    delete_option(GRIDAR_CONNECTOR_OPTION_KEY);
}


/**
 * Add a "Settings" link on the plugins list page for convenience.
 */
function gridar_connector_plugin_action_links($links) {
    $url = admin_url('options-general.php?page=gridar-connector');
    $settings_link = '<a href="' . esc_url($url) . '">Settings</a>';
    array_unshift($links, $settings_link);
    return $links;
}
add_filter(
    'plugin_action_links_' . plugin_basename(__FILE__),
    'gridar_connector_plugin_action_links'
);
